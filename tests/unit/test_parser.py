import pytest

from falasz import nodes as n
from falasz.errors import FalaszNameError, FalaszSyntaxError, Pos
from falasz.parser import MAX_NESTING, parse


def expr(src):
    """Dump of the expression in `SAY <src>`."""
    (stmt,) = parse(f"SAY {src}\n").body
    return n.dump(stmt.value)


def stmts(src):
    return n.dump(parse(src).body)


def syntax_error(src, cls=FalaszSyntaxError):
    with pytest.raises(cls) as exc:
        parse(src, "t.falasz")
    return exc.value


# ----------------------------------------------------------------- precedence


@pytest.mark.parametrize("src, tree", [
    ("1 + 2 * 3", "(+ 1 (* 2 3))"),
    ("(1 + 2) * 3", "(* (+ 1 2) 3)"),
    ("1 - 2 - 3", "(- (- 1 2) 3)"),
    ("8 / 4 / 2", "(/ (/ 8 4) 2)"),
    ("7 % 3 * 2", "(* (% 7 3) 2)"),
    ("-2 * 3", "(* (- 2) 3)"),
    ("- - 2", "(- (- 2))"),
    ("-f(x)[0]", "(- (Index (Call f [x]) 0))"),
    ("1 + 2 < 3 * 4", "(< (+ 1 2) (* 3 4))"),
    ("NOT a == b", "(NOT (== a b))"),
    ("NOT NOT a", "(NOT (NOT a))"),
    ("a OR b AND c", "(OR a (AND b c))"),
    ("a AND b OR c AND d", "(OR (AND a b) (AND c d))"),
    ("NOT a AND b", "(AND (NOT a) b)"),
    ("a == b AND c != d", "(AND (== a b) (!= c d))"),
    ("x <= 1 OR x >= 2", "(OR (<= x 1) (>= x 2))"),
])
def test_precedence(src, tree):
    assert expr(src) == tree


def test_postfix_chain():
    assert expr("m.f(1)(2)[3].g") == "(Member (Index (Call (Call (Member m 'f') [1]) [2]) 3) 'g')"


@pytest.mark.parametrize("src, tree", [
    ("42", "42"), ("3.5", "3.5"), ('"hi"', '"hi"'), ("TRUE", "TRUE"), ("FALSE", "FALSE"),
    ("NULL", "NULL"), ("[]", "(ListLit [])"), ("[1, 2,]", "(ListLit [1 2])"),
    ("{}", "(MapLit [])"), ('{"a": 1, 2: [3]}', '(MapLit [("a" 1) (2 (ListLit [3]))])'),
    ("f()", "(Call f [])"), ("f(a, b,)", "(Call f [a b])"),
    ("123456789012345678901234567890", "123456789012345678901234567890"),
])
def test_literals_and_calls(src, tree):
    assert expr(src) == tree


def test_multiline_expression_inside_brackets():
    assert expr("f(1,\n  2,\n)") == "(Call f [1 2])"


@pytest.mark.parametrize("src, col", [
    ("1 < 2 < 3", 11), ("1 == 2 != 3", 12), ("a < b == c", 11),
])
def test_comparisons_cannot_chain(src, col):
    err = syntax_error(f"SAY {src}")
    assert err.pos == Pos(1, col)
    assert "chained" in err.message


# ----------------------------------------------------------------- statements


def test_let_say_assign_call():
    assert stmts("LET a = 1\na = a + 1\nxs[0] = 2\nf(a)\nSAY a\n") == (
        "[(Let 'a' 1) (Assign a (+ a 1)) (Assign (Index xs 0) 2) "
        "(ExprStmt (Call f [a])) (Say a)]"
    )


def test_if_else_if_chain_single_end():
    src = "IF a\n SAY 1\nELSE IF b\n SAY 2\nELSE IF c\nELSE\n SAY 3\nEND\n"
    assert stmts(src) == (
        "[(If a [(Say 1)] [(If b [(Say 2)] [(If c [] [(Say 3)])])])]"
    )


def test_if_without_else():
    assert stmts("IF a\nEND\n") == "[(If a [] None)]"


def test_while_for_break_continue():
    src = "WHILE a\n BREAK\nEND\nFOR x IN xs\n CONTINUE\nEND\n"
    assert stmts(src) == "[(While a [(Break)]) (For 'x' xs [(Continue)])]"


def test_func_return():
    src = "FUNC f(a, b)\n RETURN a + b\nEND\nFUNC g()\n RETURN\nEND\n"
    assert stmts(src) == "[(Func 'f' [('a') ('b')] [(Return (+ a b))]) (Func 'g' [] [(Return None)])]"


def test_import_forms():
    src = "IMPORT files\nIMPORT LOCAL util\nIMPORT files AS f\nIMPORT LOCAL files AS my_files\n"
    imports = parse(src).body
    assert [(i.module, i.local, i.alias, i.binding) for i in imports] == [
        ("files", False, None, "files"),
        ("util", True, None, "util"),
        ("files", False, "f", "f"),
        ("files", True, "my_files", "my_files"),
    ]
    assert imports[3].pos == Pos(4, 1)
    assert imports[3].binding_pos == Pos(4, 23)
    assert imports[1].binding_pos == Pos(2, 14)


def test_export():
    (export,) = parse("EXPORT a, b_2\n").body
    assert export.names == [("a", Pos(1, 8)), ("b_2", Pos(1, 11))]


def test_positions_follow_spec_rules():
    prog = parse('LET x = a + b\nSAY f(1)[2]\nSAY m.k\n')
    let, call_say, member_say = prog.body
    assert let.pos == Pos(1, 1) and let.name_pos == Pos(1, 5)
    assert let.value.pos == Pos(1, 11)  # operator
    assert n.start(let.value) == Pos(1, 9)
    index = call_say.value
    assert index.pos == Pos(2, 9) and index.target.pos == Pos(2, 6)
    assert member_say.value.pos == Pos(3, 6) and member_say.value.name_pos == Pos(3, 7)


def test_comments_and_blank_lines_everywhere():
    src = "\n# head\nIF a # c\n\n  # inside\n  SAY 1 # c\n\nEND # c\n\n"
    assert stmts(src) == "[(If a [(Say 1)] None)]"


def test_crlf_source():
    assert stmts("IF a\r\n SAY 1\r\nELSE\r\n SAY 2\r\nEND\r\n") == "[(If a [(Say 1)] [(Say 2)])]"


def test_empty_program():
    assert parse("").body == []


# --------------------------------------------------------------- syntax errors


@pytest.mark.parametrize("src, pos, fragment", [
    ("RETURN 1", (1, 1), "RETURN outside"),
    ("IF TRUE\n RETURN\nEND", (2, 2), "RETURN outside"),
    ("BREAK", (1, 1), "BREAK outside"),
    ("CONTINUE", (1, 1), "CONTINUE outside"),
    ("FOR x IN y\n FUNC f()\n  CONTINUE\n END\nEND", (3, 3), "CONTINUE outside"),
    ("FUNC f()\n IMPORT files\nEND", (2, 2), "top level"),
    ("WHILE TRUE\n EXPORT a\nEND", (2, 2), "top level"),
    ("FUNC f(a, b, a)\nEND", (1, 14), "duplicate parameter"),
    ("1 + 2", (1, 1), "no effect"),
    ("x", (1, 1), "no effect"),
    ("(f)", (1, 2), "no effect"),
    ("f() = 1", (1, 1), "invalid assignment target"),
    ("1 = 2", (1, 1), "invalid assignment target"),
    ("IF TRUE\n SAY 1\n", (3, 1), "expected END or ELSE"),
    ("FUNC f()\n", (2, 1), "expected END"),
    ("IF TRUE\nELSE\nELSE\nEND", (3, 1), "'ELSE' without a matching IF"),
    ("WHILE TRUE\nELSE\nEND", (2, 1), "'ELSE' without a matching IF"),
    ("END", (1, 1), "'END' without a matching block"),
    ("ELSE", (1, 1), "'ELSE' without a matching IF"),
    ("SAY", (1, 4), "expected an expression"),
    ("SAY 1 2", (1, 7), "expected end of line"),
    ("IF TRUE SAY 1\nEND", (1, 9), "expected end of line"),
    ("LET = 1", (1, 5), "expected variable name"),
    ("LET a 1", (1, 7), "expected '='"),
    ("LET a = (1", (1, 11), "expected ')'"),
    ("SAY [1, 2", (1, 10), "expected ']'"),
    ("SAY {1 2}", (1, 8), "expected ':'"),
    ("FOR x xs\nEND", (1, 7), "expected 'IN'"),
    ("FUNC f(1)\nEND", (1, 8), "expected parameter name"),
    ("IMPORT", (1, 7), "expected module name"),
    ("IMPORT LOCAL m AS", (1, 18), "expected alias name"),
    ("IMPORT m.n", (1, 9), "expected end of line"),
    ("EXPORT a,", (1, 10), "expected name to export"),
    ("SAY m.1", (1, 7), "expected member name"),
    ("SAY 1.", (1, 5), "invalid float"),
])
def test_syntax_errors(src, pos, fragment):
    err = syntax_error(src)
    assert err.pos == Pos(*pos), err.format()
    assert fragment in err.message, err.format()


def test_assignment_to_module_member_is_name_error():
    err = syntax_error("m.x = 1", FalaszNameError)
    assert err.pos == Pos(1, 2)
    assert "read-only" in err.message


def test_return_and_break_allowed_where_valid():
    src = "FUNC f()\n WHILE TRUE\n  IF TRUE\n   BREAK\n  END\n  RETURN 1\n END\nEND\n"
    parse(src)


def test_break_in_loop_inside_function_inside_loop():
    parse("WHILE TRUE\n FUNC f()\n  FOR x IN y\n   BREAK\n  END\n END\n BREAK\nEND\n")


# -------------------------------------------------------------------- limits


def test_nesting_limit_parentheses():
    deep_ok = "(" * (MAX_NESTING - 2) + "1" + ")" * (MAX_NESTING - 2)
    parse(f"SAY {deep_ok}\n")
    too_deep = "(" * (MAX_NESTING + 5) + "1" + ")" * (MAX_NESTING + 5)
    assert "nesting too deep" in syntax_error(f"SAY {too_deep}\n").message


def test_nesting_limit_unary_and_blocks():
    assert "nesting too deep" in syntax_error("SAY " + "-" * (MAX_NESTING + 5) + "1").message
    blocks = "IF TRUE\n" * (MAX_NESTING + 5) + "END\n" * (MAX_NESTING + 5)
    assert "nesting too deep" in syntax_error(blocks).message


def test_nesting_limit_is_reached_before_python_recursion_limit():
    # Must be a clean FalaszSyntaxError, never RecursionError.
    for src in ["[" * 5000, "NOT " * 5000 + "a", "f(" * 5000]:
        with pytest.raises(FalaszSyntaxError):
            parse(src)


def test_recursion_limit_restored():
    import sys
    before = sys.getrecursionlimit()
    parse("SAY 1\n")
    with pytest.raises(FalaszSyntaxError):
        parse("SAY (")
    assert sys.getrecursionlimit() == before
