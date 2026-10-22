import io
import sys

import pytest

from falasz.errors import FalaszError
from falasz.runtime import StaticErrors, run_source


def run(src, stdin=None, max_steps=None):
    out = io.StringIO()
    inp = io.BytesIO(stdin) if stdin is not None else None
    run_source(src, "t.falasz", out=out, inp=inp, max_steps=max_steps)
    return out.getvalue()


def say(expr):
    return run(f"SAY {expr}\n").rstrip("\n")


def error(src, stdin=None, max_steps=None):
    with pytest.raises((FalaszError, StaticErrors)) as exc:
        run(src, stdin, max_steps)
    err = exc.value.errors[0] if isinstance(exc.value, StaticErrors) else exc.value
    return err.category, err.pos.line, err.pos.column, err.message


def assert_error(src, category, line, col, fragment="", **kw):
    got = error(src, **kw)
    assert got[:3] == (category, line, col), got
    assert fragment in got[3], got


# ------------------------------------------------------------- arithmetic


@pytest.mark.parametrize("expr, out", [
    ("1 + 2", "3"), ("2 - 5", "-3"), ("3 * 4", "12"), ("7 / 2", "3.5"), ("6 / 3", "2.0"),
    ("1 / 3", "0.3333333333333333"), ("-7 % 3", "2"), ("7 % -3", "-2"), ("-7 % -3", "-1"),
    ("7.5 % 2", "1.5"), ("-7.5 % 2", "0.5"), ("1 + 0.5", "1.5"), ("2 * 0.5", "1.0"),
    ("0.1 + 0.2", "0.30000000000000004"), ("10 - 2.5", "7.5"), ("-(-3)", "3"), ("-0", "0"),
    ("2 * 3 + 4 * 5", "26"), ("100 / 10 / 2", "5.0"), ("1 - -1", "2"),
])
def test_arithmetic(expr, out):
    assert say(expr) == out


def test_big_integers_are_exact():
    assert say("99999999999999999999 * 99999999999999999999") == "9999999999999999999800000000000000000001"
    assert say("12345678901234567890123 % 97") == str(12345678901234567890123 % 97)


def test_int_float_division_is_correctly_rounded_for_big_ints():
    assert say("10000000000000000000001 / 10000000000000000000000") == "1.0"


@pytest.mark.parametrize("expr, out", [
    ("1.0", "1.0"), ("0.1", "0.1"), ("100000000000000000000.0", "100000000000000000000.0"),
    ("FLOAT(10000000000000000000000)", "10000000000000000000000.0"),
    ("0.0000001", "0.0000001"), ("1.5 / 10000000", "0.00000015"),
    ("-0.0", "-0.0"), ("-0.0 == 0.0", "TRUE"), ("2.50", "2.5"),
])
def test_float_formatting_never_uses_exponent(expr, out):
    assert say(expr) == out


@pytest.mark.parametrize("expr, col, category", [
    ("1 / 0", 7, "ZeroDivisionError"), ("1 / 0.0", 7, "ZeroDivisionError"),
    ("1.5 / 0", 9, "ZeroDivisionError"), ("5 % 0", 7, "ZeroDivisionError"),
    ("5.0 % 0.0", 9, "ZeroDivisionError"),
])
def test_division_by_zero(expr, col, category):
    assert_error(f"SAY {expr}\n", category, 1, col)


def test_float_overflow_is_arithmetic_error():
    big = "9" * 400
    assert_error(f"SAY {big} * 1.0\n", "ArithmeticError", 1, 406)
    assert_error(f"SAY {big} / 1\n", "ArithmeticError", 1, 406)
    assert_error("LET f = 100000000000000000000000000000000000000000000000000.0\n"
                 "LET g = f * f * f * f * f * f * f\n", "ArithmeticError", 2, 31)
    assert_error(f"SAY FLOAT({big})\n", "ArithmeticError", 1, 10)
    assert_error(f'SAY FLOAT("{big}")\n', "ArithmeticError", 1, 10)


@pytest.mark.parametrize("expr, col", [
    ('"a" + 1', 9), ('1 + "a"', 7), ("TRUE + 1", 10), ("NULL + 1", 10), ("[1] + 1", 9),
    ('"ab" * 2', 10), ("[1] * 2", 9), ("1 - TRUE", 7), ('- "a"', 5), ("-TRUE", 5),
    ('{} + {}', 8), ('"a" - "a"', 9), ("1 % NULL", 7), ("1 / FALSE", 7),
])
def test_no_implicit_conversions(expr, col):
    assert_error(f"SAY {expr}\n", "TypeError", 1, col, "unsupported operand")


def test_concatenation():
    assert say('"Ala" + " " + "ma"') == "Ala ma"
    assert say("[1] + [2, [3]] + []") == "[1, 2, [3]]"


def test_list_concatenation_creates_new_list():
    assert run("LET a = [1]\nLET b = a + []\nb[0] = 9\nSAY a\n") == "[1]\n"


# -------------------------------------------------------------- comparison


@pytest.mark.parametrize("expr, out", [
    ("1 < 2", "TRUE"), ("2 <= 2", "TRUE"), ("3 > 4", "FALSE"), ("4 >= 4.0", "TRUE"),
    ("1 < 1.5", "TRUE"), ('"a" < "b"', "TRUE"), ('"B" < "a"', "TRUE"), ('"" < "a"', "TRUE"),
    ('"ab" < "b"', "TRUE"), ('"ż" > "z"', "TRUE"),
    ("9007199254740993 == 9007199254740992.0", "FALSE"),  # exact int/float comparison
    ("9007199254740993 > 9007199254740992.0", "TRUE"),
])
def test_ordering(expr, out):
    assert say(expr) == out


@pytest.mark.parametrize("expr, col", [
    ('1 < "2"', 7), ("TRUE < FALSE", 10), ("NULL < 1", 10), ("[1] < [2]", 9), ('"a" >= 1', 9),
])
def test_ordering_type_errors(expr, col):
    assert_error(f"SAY {expr}\n", "TypeError", 1, col, "cannot compare")


@pytest.mark.parametrize("expr, out", [
    ("1 == 1.0", "TRUE"), ("1 != 1.0", "FALSE"), ('1 == "1"', "FALSE"), ("TRUE == 1", "FALSE"),
    ("FALSE == 0", "FALSE"), ("NULL == NULL", "TRUE"), ("NULL == FALSE", "FALSE"),
    ("[1, 2] == [1, 2]", "TRUE"), ("[1, 2] == [2, 1]", "FALSE"), ("[1] == [1.0]", "TRUE"),
    ("[TRUE] == [1]", "FALSE"), ("[] == {}", "FALSE"), ('{"a": [1]} == {"a": [1]}', "TRUE"),
    ('{"a": 1, "b": 2} == {"b": 2, "a": 1}', "TRUE"), ("{1: 1} == {TRUE: 1}", "FALSE"),
    ("{1: 1} == {1: 2}", "FALSE"), ("LEN == LEN", "TRUE"), ("LEN == STR", "FALSE"),
    ('"a" != "b"', "TRUE"),
])
def test_equality(expr, out):
    assert say(expr) == out


# -------------------------------------------------------------- booleans


@pytest.mark.parametrize("expr, out", [
    ("TRUE AND FALSE", "FALSE"), ("TRUE OR FALSE", "TRUE"), ("NOT TRUE", "FALSE"),
    ("NOT FALSE AND FALSE", "FALSE"), ("NOT (FALSE AND FALSE)", "TRUE"),
    ("FALSE OR FALSE OR TRUE", "TRUE"), ("1 < 2 AND 2 < 3", "TRUE"),
])
def test_boolean_logic(expr, out):
    assert say(expr) == out


def test_short_circuit_skips_right_operand():
    # The right operands would fail (division by zero / wrong type) if evaluated.
    assert say("FALSE AND 1 / 0 == 1") == "FALSE"
    assert say("TRUE OR 1") == "TRUE"


@pytest.mark.parametrize("expr, col, fragment", [
    ("1 AND TRUE", 5, "operand of AND"), ("TRUE AND 1", 14, "operand of AND"),
    ("FALSE OR NULL", 14, "operand of OR"), ('"x" OR TRUE', 5, "operand of OR"),
    ("NOT 0", 9, "operand of NOT"), ("NOT [1]", 9, "operand of NOT"),
])
def test_boolean_operators_require_booleans(expr, col, fragment):
    assert_error(f"SAY {expr}\n", "TypeError", 1, col, fragment)


@pytest.mark.parametrize("cond", ["1", "0", '""', "[]", "NULL", '"TRUE"'])
def test_conditions_require_booleans(cond):
    assert_error(f"IF {cond}\nEND\n", "TypeError", 1, 4, "IF condition must be BOOLEAN")
    assert_error(f"WHILE {cond}\nEND\n", "TypeError", 1, 7, "WHILE condition must be BOOLEAN")


def test_else_if_condition_checked_only_when_reached():
    assert run("IF TRUE\n SAY 1\nELSE IF 5\n SAY 2\nEND\n") == "1\n"
    assert_error("IF FALSE\nELSE IF 5\nEND\n", "TypeError", 2, 9)


# ------------------------------------------------------------ control flow


def test_if_else_chain():
    src = ("FOR n IN [1, 2, 3, 4]\n IF n == 1\n  SAY \"one\"\n ELSE IF n == 2\n  SAY \"two\"\n"
           " ELSE IF n == 3\n  SAY \"three\"\n ELSE\n  SAY \"many\"\n END\nEND\n")
    assert run(src) == "one\ntwo\nthree\nmany\n"


def test_while_break_continue():
    src = ("LET i = 0\nWHILE i < 10\n i = i + 1\n IF i % 2 == 1\n  CONTINUE\n END\n"
           " IF i > 6\n  BREAK\n END\n SAY i\nEND\nSAY i\n")
    assert run(src) == "2\n4\n6\n8\n"


def test_break_only_exits_innermost_loop():
    src = "FOR a IN [1, 2]\n FOR b IN [1, 2, 3]\n  IF b == 2\n   BREAK\n  END\n  SAY STR(a) + STR(b)\n END\nEND\n"
    assert run(src) == "11\n21\n"


def test_continue_in_for():
    assert run("FOR x IN RANGE(0, 5)\n IF x == 2\n  CONTINUE\n END\n SAY x\nEND\n") == "0\n1\n3\n4\n"


def test_for_over_list_string_map():
    assert run('FOR c IN "żó"\n SAY c\nEND\n') == "ż\nó\n"
    assert run('FOR k IN {"b": 1, "a": 2, 3: 3}\n SAY k\nEND\n') == "b\na\n3\n"
    assert run("FOR x IN []\n SAY x\nEND\nFOR x IN \"\"\nEND\nFOR x IN {}\nEND\n") == ""


def test_for_iterates_over_snapshot():
    src = "LET xs = [1, 2]\nFOR x IN xs\n xs = xs + [x]\n SAY x\nEND\nSAY xs\n"
    assert run(src) == "1\n2\n[1, 2, 1, 2]\n"
    src = 'LET m = {"a": 1}\nFOR k IN m\n m["b"] = 2\n SAY k\nEND\nSAY LEN(m)\n'
    assert run(src) == "a\n2\n"


def test_for_variable_keeps_last_value_and_is_shared():
    assert run("FOR i IN [1, 2]\nEND\nSAY i\nFOR i IN [7]\nEND\nSAY i\n") == "2\n7\n"


def test_for_variable_keeps_value_after_break():
    assert run("FOR i IN [1, 2, 3]\n IF i == 2\n  BREAK\n END\nEND\nSAY i\n") == "2\n"


@pytest.mark.parametrize("value", ["5", "2.5", "TRUE", "NULL", "LEN"])
def test_for_over_non_iterable(value):
    assert_error(f"FOR x IN {value}\nEND\n", "TypeError", 1, 10, "cannot iterate")


def test_empty_blocks():
    assert run("IF TRUE\nELSE\nEND\nWHILE FALSE\nEND\nFOR x IN [1]\nEND\n") == ""


# ------------------------------------------------- variables & scopes (N2)


def test_variables_from_blocks_visible_after():
    assert run("IF TRUE\n LET a = 1\nEND\nSAY a\nWHILE TRUE\n LET b = 2\n BREAK\nEND\nSAY b\n") == "1\n2\n"


def test_variable_from_unexecuted_branch_does_not_exist():
    assert_error("IF FALSE\n LET a = 1\nEND\nSAY a\n", "NameError", 4, 5, "does not exist")
    assert_error("IF FALSE\n LET a = 1\nEND\na = 2\n", "NameError", 4, 1, "does not exist")
    assert_error("IF FALSE\n LET a = [1]\nEND\na[0] = 2\n", "NameError", 4, 1, "does not exist")


def test_variable_from_other_branch_exists():
    assert run("IF FALSE\n LET a = 1\nELSE\n LET b = 2\nEND\nSAY b\n") == "2\n"


def test_for_variable_does_not_exist_without_iterations():
    assert_error("FOR i IN []\nEND\nSAY i\n", "NameError", 3, 5, "does not exist")


def test_let_re_executed_in_loop_rebinds():
    assert run("LET s = 0\nFOR i IN [1, 2, 3]\n LET d = i * 10\n s = s + d\nEND\nSAY s\nSAY d\n") == "60\n30\n"


def test_assignment_evaluates_right_side_first():
    # The right side runs (and consumes input) before the missing target is detected.
    src = 'IF FALSE\n LET a = 1\nEND\na = INPUT("p> ")\n'
    out = io.StringIO()
    with pytest.raises(FalaszError):
        run_source(src, "t.falasz", out=out, inp=io.BytesIO(b"x\n"))
    assert out.getvalue() == "p> "


def test_static_errors_prevent_execution():
    out = io.StringIO()
    with pytest.raises(StaticErrors) as exc:
        run_source('SAY "side effect"\nSAY missing\n', "t.falasz", out=out)
    assert out.getvalue() == ""
    assert exc.value.errors[0].format() == "t.falasz:2:5: NameError: 'missing' is not declared"


def test_not_yet_implemented_features_are_reported():
    assert error("IMPORT files\n")[0] == "NotImplementedError"


# ----------------------------------------------------- lists, maps, indexing


def test_list_indexing_and_assignment():
    assert run("LET xs = [10, 20, 30]\nxs[1] = 99\nSAY xs[1]\nSAY xs[2]\nSAY xs\n") == "99\n30\n[10, 99, 30]\n"


def test_lists_are_references():
    assert run("LET a = [1]\nLET b = a\nb[0] = 2\nSAY a\n") == "[2]\n"


@pytest.mark.parametrize("index, category, fragment", [
    ("3", "IndexError", "out of range"), ("-1", "IndexError", "out of range"),
    ("1.0", "TypeError", "index must be INTEGER"), ("TRUE", "TypeError", "index must be INTEGER"),
    ('"0"', "TypeError", "index must be INTEGER"),
])
def test_bad_list_index(index, category, fragment):
    assert_error(f"LET xs = [1, 2, 3]\nSAY xs[{index}]\n", category, 2, 7, fragment)
    assert_error(f"LET xs = [1, 2, 3]\nxs[{index}] = 0\n", category, 2, 3, fragment)


def test_index_into_empty_list():
    assert_error("SAY [][0]\n", "IndexError", 1, 7)


def test_string_indexing():
    assert say('"zażółć"[2]') == "ż"
    assert_error('SAY "abc"[3]\n', "IndexError", 1, 10)
    assert_error('LET s = "abc"\ns[0] = "x"\n', "TypeError", 2, 2, "immutable")


def test_maps():
    src = 'LET m = {"a": 1}\nm["b"] = 2\nm["a"] = 3\nm[1] = "int"\nm[TRUE] = "bool"\nSAY m\nSAY m[1]\nSAY m[TRUE]\nSAY LEN(m)\n'
    assert run(src) == '{"a": 3, "b": 2, 1: "int", TRUE: "bool"}\nint\nbool\n4\n'


def test_map_keys_true_and_1_are_distinct():
    assert say("{1: \"one\", TRUE: \"true\", 0: \"zero\", FALSE: \"false\"}") == \
        '{1: "one", TRUE: "true", 0: "zero", FALSE: "false"}'


def test_map_literal_duplicate_key_last_wins_first_position():
    assert say('{"a": 1, "b": 2, "a": 3}') == '{"a": 3, "b": 2}'


@pytest.mark.parametrize("key", ["1.5", "NULL", "[1]", "{}"])
def test_bad_map_keys(key):
    assert_error(f"LET m = {{{key}: 1}}\n", "TypeError", 1, 10, "map keys must be")
    assert_error(f"LET m = {{}}\nSAY m[{key}]\n", "TypeError", 2, 6, "map keys must be")
    assert_error(f"LET m = {{}}\nm[{key}] = 1\n", "TypeError", 2, 2, "map keys must be")


def test_missing_map_key():
    assert_error('LET m = {"a": 1}\nSAY m["b"]\n', "KeyError", 2, 6, 'key "b" not found')
    assert_error('LET m = {1: 1}\nSAY m[TRUE]\n', "KeyError", 2, 6, "key TRUE not found")


@pytest.mark.parametrize("value", ["5", "NULL", "TRUE", "2.5", "LEN"])
def test_indexing_unsupported_types(value):
    assert_error(f"SAY {value}[0]\n", "TypeError", 1, 5 + len(value), "cannot be indexed")


def test_member_access_on_non_module():
    assert_error("LET x = 1\nSAY x.y\n", "TypeError", 2, 6, "has no members")


def test_nested_structures():
    assert run('LET m = {"xs": [1, {"k": [2]}]}\nm["xs"][1]["k"][0] = 3\nSAY m\n') == \
        '{"xs": [1, {"k": [3]}]}\n'


# -------------------------------------------------- representation edge cases


def test_string_representation_inside_containers():
    assert say(r'["a\"b", "c\\d", "e\nf", "g\th"]') == r'["a\"b", "c\\d", "e\nf", "g\th"]'
    assert run(r'SAY "a\"b\\c"' + "\n") == 'a"b\\c\n'


def test_cyclic_structures():
    assert run("LET xs = [1]\nxs[0] = xs\nSAY xs\n") == "[[...]]\n"
    assert run('LET m = {}\nm["self"] = m\nSAY m\n') == '{"self": {...}}\n'
    assert run("LET a = [0]\nLET b = [0]\na[0] = a\nb[0] = b\nSAY a == b\n") == "TRUE\n"


def test_shared_but_not_cyclic_structure_prints_fully():
    assert run("LET x = [1]\nSAY [x, x]\n") == "[[1], [1]]\n"


def test_deeply_nested_values_hit_limit_not_python_recursion():
    src = "LET xs = []\nFOR i IN RANGE(0, 2000)\n xs = [xs]\nEND\nSAY LEN(xs)\nSAY xs\n"
    assert_error(src, "LimitError", 6, 1, "nested too deeply")
    src = "LET a = []\nLET b = []\nFOR i IN RANGE(0, 2000)\n a = [a]\n b = [b]\nEND\nSAY a == b\n"
    assert_error(src, "LimitError", 7, 7, "nested too deeply")


def test_huge_integer_text_conversion_limit():
    digits = sys.get_int_max_str_digits()
    assert_error(f"SAY {'1' * (digits + 1)}\n", "LimitError", 1, 5, "too many digits")
    src = "LET x = 1\nFOR i IN RANGE(0, 15000)\n x = x * 10\nEND\nSAY x\n"
    assert_error(src, "LimitError", 5, 1, "too many digits")
    assert_error(f'SAY INT("{"1" * (digits + 1)}")\n', "LimitError", 1, 8, "too many digits")


# ----------------------------------------------------------------- builtins


@pytest.mark.parametrize("expr, out", [
    ("STR(42)", "42"), ("STR(2.0)", "2.0"), ('STR("x")', "x"), ("STR(NULL)", "NULL"),
    ("STR(TRUE)", "TRUE"), ('STR([1, "a"])', '[1, "a"]'), ("STR(LEN)", "<builtin LEN>"),
    ("LEN(STR(12345))", "5"),
    ('INT("42")', "42"), ('INT("-7")', "-7"), ('INT("007")', "7"), ('INT("-0")', "0"),
    ("INT(3.99)", "3"), ("INT(-3.99)", "-3"), ("INT(5)", "5"),
    ('FLOAT("2.5")', "2.5"), ('FLOAT("-3")', "-3.0"), ('FLOAT("007.50")', "7.5"), ("FLOAT(2)", "2.0"),
    ('LEN("")', "0"), ('LEN("zażółć")', "6"), ('LEN("🙂")', "1"), ("LEN([1, [2, 3]])", "2"),
    ('LEN({"a": 1})', "1"),
    ("RANGE(0, 3)", "[0, 1, 2]"), ("RANGE(3, 0)", "[]"), ("RANGE(5, 5)", "[]"),
    ("RANGE(0, 10, 3)", "[0, 3, 6, 9]"), ("RANGE(3, 0, -1)", "[3, 2, 1]"), ("RANGE(-2, 1)", "[-2, -1, 0]"),
])
def test_builtins(expr, out):
    assert say(expr) == out


@pytest.mark.parametrize("call, category, fragment", [
    ('INT("")', "ValueError", "cannot convert"), ('INT(" 5")', "ValueError", "cannot convert"),
    ('INT("5 ")', "ValueError", "cannot convert"), ('INT("+5")', "ValueError", "cannot convert"),
    ('INT("1.5")', "ValueError", "cannot convert"), ('INT("١٢")', "ValueError", "cannot convert"),
    ("INT(TRUE)", "TypeError", "cannot convert BOOLEAN"), ("INT(NULL)", "TypeError", "cannot convert NULL"),
    ('FLOAT("1e5")', "ValueError", "cannot convert"), ('FLOAT(".5")', "ValueError", "cannot convert"),
    ('FLOAT("nan")', "ValueError", "cannot convert"), ('FLOAT("inf")', "ValueError", "cannot convert"),
    ("FLOAT(TRUE)", "TypeError", "cannot convert BOOLEAN"), ("FLOAT([1])", "TypeError", "cannot convert"),
    ("LEN(5)", "TypeError", "LEN expects"), ("LEN(NULL)", "TypeError", "LEN expects"),
    ("RANGE(0, 2.0)", "TypeError", "INTEGER"), ("RANGE(TRUE, 2)", "TypeError", "INTEGER"),
    ("RANGE(0, 5, 0)", "ValueError", "step"), ("RANGE(0, 10000001)", "LimitError", "RANGE would have"),
])
def test_builtin_errors_point_at_call_paren(call, category, fragment):
    paren = call.index("(")
    assert_error(f"SAY {call}\n", category, 1, 5 + paren, fragment)


def test_range_limit_boundary():
    assert run("LET r = RANGE(0, 10000000)\nSAY LEN(r)\n") == "10000000\n"


@pytest.mark.parametrize("call, fragment", [
    ("LEN()", "LEN expects 1 argument(s), got 0"), ("LEN(1, 2)", "expects 1 argument(s), got 2"),
    ("RANGE(1)", "RANGE expects 2 to 3 argument(s), got 1"), ("RANGE(1, 2, 3, 4)", "got 4"),
    ('INPUT("a", "b")', "INPUT expects 0 to 1"), ("STR()", "STR expects 1"),
])
def test_builtin_arity(call, fragment):
    assert_error(f"SAY {call}\n", "ArityError", 1, 5 + call.index("("), fragment)


def test_builtins_are_values():
    assert run("LET f = LEN\nSAY f([1, 2])\nSAY f\n") == "2\n<builtin LEN>\n"


@pytest.mark.parametrize("value", ["1", '"LEN"', "NULL", "[LEN]"])
def test_calling_non_function(value):
    assert_error(f"LET f = {value}\nf()\n", "TypeError", 2, 2, "is not callable")


def test_builtin_call_as_statement():
    assert run("LEN([1])\nSAY 1\n") == "1\n"


# -------------------------------------------------------------------- INPUT


def test_input_basic():
    src = 'LET a = INPUT("? ")\nLET b = INPUT()\nSAY a + "|" + b\n'
    assert run(src, stdin=b"first\nsecond\n") == "? first|second\n"


def test_input_strips_only_line_ending():
    src = "SAY \"[\" + INPUT() + \"]\"\nSAY \"[\" + INPUT() + \"]\"\nSAY \"[\" + INPUT() + \"]\"\n"
    assert run(src, stdin=b"  spaced  \r\n\n\tx\r") == "[  spaced  ]\n[]\n[\tx\r]\n"


def test_input_eof_returns_null():
    assert run("SAY INPUT()\nSAY INPUT()\n", stdin=b"last-without-newline") == "last-without-newline\nNULL\n"
    assert run("SAY INPUT()\n", stdin=b"") == "NULL\n"
    assert run("SAY INPUT()\n") == "NULL\n"  # no input stream at all


def test_input_loop_until_eof():
    src = "LET total = 0\nLET line = INPUT()\nWHILE line != NULL\n total = total + INT(line)\n line = INPUT()\nEND\nSAY total\n"
    assert run(src, stdin=b"1\n2\n39\n") == "42\n"


def test_input_utf8():
    assert run("SAY LEN(INPUT())\n", stdin="zażółć\n".encode()) == "6\n"
    assert_error("SAY INPUT()\n", "ValueError", 1, 10, "not valid UTF-8", stdin=b"\xff\n")


def test_input_prompt_type():
    assert_error("SAY INPUT(5)\n", "TypeError", 1, 10, "prompt must be STRING")


def test_input_empty_prompt_and_prompt_without_newline():
    assert run('LET a = INPUT("")\nLET b = INPUT(">")\n', stdin=b"x\ny\n") == ">"


# ----------------------------------------------------------- resource limits


def test_step_limit_stops_infinite_loop():
    assert_error("WHILE TRUE\nEND\n", "LimitError", 1, 1, "step limit of 1000", max_steps=1000)


def test_step_limit_counts_statements():
    run("SAY 1\nSAY 2\n", max_steps=2)
    assert_error("SAY 1\nSAY 2\nSAY 3\n", "LimitError", 3, 1, max_steps=2)


def test_deep_expression_evaluates():
    deep = "(" * 190 + "1" + " + 1)" * 190
    assert say(deep) == "191"
