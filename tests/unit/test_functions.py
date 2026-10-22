"""Stage 4: user functions — recursion, scopes, arguments, RETURN, call-stack traces."""

import io

import pytest

from falasz.errors import FalaszError
from falasz.interpreter import MAX_CALL_DEPTH, Interpreter
from falasz.parser import parse
from falasz.runtime import StaticErrors, run_source
from falasz.validator import validate


def run(src, stdin=None, max_steps=None):
    out = io.StringIO()
    run_source(src, "t.falasz", out=out, inp=io.BytesIO(stdin) if stdin else None, max_steps=max_steps)
    return out.getvalue()


def lines(*items):
    return "".join(f"{i}\n" for i in items)


def fail(src, **kw):
    with pytest.raises((FalaszError, StaticErrors)) as exc:
        run(src, **kw)
    return exc.value.errors[0] if isinstance(exc.value, StaticErrors) else exc.value


def at(src, line, needle, nth=1):
    """(line, column) of the nth occurrence of `needle` on 1-based `line` of `src`."""
    text = src.split("\n")[line - 1]
    col = -1
    for _ in range(nth):
        col = text.index(needle, col + 1)
    return (line, col + 1)


def assert_fail(src, category, where, fragment=""):
    err = fail(src)
    assert (err.category, tuple(err.pos)) == (category, where), err.format_with_trace()
    assert fragment in err.message, err.message
    return err


# ================================================================= RETURN


def test_return_value_and_implicit_null():
    src = """FUNC one()
    RETURN 1
END
FUNC bare()
    RETURN
END
FUNC nothing()
    LET x = 1
END
FUNC empty()
END
SAY one()
SAY bare()
SAY nothing()
SAY empty()
"""
    assert run(src) == lines(1, "NULL", "NULL", "NULL")


@pytest.mark.parametrize("value, shown", [
    ("2.5", "2.5"), ('"txt"', "txt"), ("TRUE", "TRUE"), ("NULL", "NULL"),
    ("[1, [2]]", "[1, [2]]"), ('{"k": 1}', '{"k": 1}'), ("LEN", "<builtin LEN>"),
])
def test_return_any_type(value, shown):
    assert run(f"FUNC f()\n    RETURN {value}\nEND\nSAY f()\n") == shown + "\n"


def test_code_after_return_is_not_executed():
    src = 'FUNC f()\n    SAY "before"\n    RETURN 1\n    SAY "after"\nEND\nSAY f()\n'
    assert run(src) == lines("before", 1)


def test_return_from_inside_loops_stops_all_loops():
    src = """FUNC find(xs, wanted)
    LET i = 0
    WHILE TRUE
        FOR x IN xs
            IF x == wanted
                RETURN i
            END
            i = i + 1
        END
        RETURN -1
    END
    SAY "unreachable"
END
SAY find([5, 6, 7], 7)
SAY find([5, 6, 7], 9)
"""
    assert run(src) == lines(2, -1)


def test_return_from_else_if_branches():
    src = """FUNC sign(n)
    IF n > 0
        RETURN "plus"
    ELSE IF n < 0
        RETURN "minus"
    END
    RETURN "zero"
END
SAY sign(5)
SAY sign(-2.5)
SAY sign(0)
"""
    assert run(src) == lines("plus", "minus", "zero")


def test_return_in_nested_function_returns_only_from_inner():
    src = """FUNC outer()
    FUNC inner()
        RETURN "inner"
    END
    LET got = inner()
    RETURN "outer got " + got
END
SAY outer()
"""
    assert run(src) == lines("outer got inner")


def test_loop_after_inner_return_continues_normally():
    src = """FUNC id(x)
    FOR i IN [1, 2, 3]
        RETURN x
    END
END
LET total = 0
FOR n IN [1, 2, 3]
    total = total + id(n)
END
SAY total
"""
    assert run(src) == lines(6)


def test_return_outside_function_is_rejected_statically():
    src = "IF TRUE\n    RETURN 1\nEND\n"
    assert_fail(src, "SyntaxError", at(src, 2, "RETURN"), "outside of a function")


def test_break_inside_function_cannot_leave_callers_loop():
    src = "WHILE TRUE\n    FUNC f()\n        BREAK\n    END\nEND\n"
    assert_fail(src, "SyntaxError", at(src, 3, "BREAK"), "outside of a loop")


def test_error_in_return_expression_is_located():
    src = "FUNC f()\n    RETURN 1 + TRUE\nEND\nf()\n"
    assert_fail(src, "TypeError", at(src, 2, "+"))


# ============================================================== recursion


def test_factorial_and_big_integers():
    src = """FUNC fact(n)
    IF n <= 1
        RETURN 1
    END
    RETURN n * fact(n - 1)
END
SAY fact(0)
SAY fact(5)
SAY fact(30)
"""
    assert run(src) == lines(1, 120, 265252859812191058636308480000000)


def test_fibonacci_tree_recursion():
    src = """FUNC fib(n)
    IF n < 2
        RETURN n
    END
    RETURN fib(n - 1) + fib(n - 2)
END
LET out = []
FOR i IN RANGE(0, 15)
    out = out + [fib(i)]
END
SAY out
"""
    assert run(src) == "[0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377]\n"


def test_mutual_recursion_defined_in_either_order():
    src = """FUNC is_even(n)
    IF n == 0
        RETURN TRUE
    END
    RETURN is_odd(n - 1)
END
FUNC is_odd(n)
    IF n == 0
        RETURN FALSE
    END
    RETURN is_even(n - 1)
END
SAY is_even(10)
SAY is_odd(7)
SAY is_even(7)
"""
    assert run(src) == lines("TRUE", "TRUE", "FALSE")


def test_each_recursive_call_has_its_own_locals():
    src = """FUNC depth(n)
    LET mine = n * 10
    IF n > 0
        depth(n - 1)
    END
    SAY mine
END
depth(3)
"""
    assert run(src) == lines(0, 10, 20, 30)


def test_recursion_over_nested_lists():
    src = """FUNC total(x)
    IF x == []
        RETURN 0
    END
    LET sum = 0
    FOR item IN x
        IF STR(item)[0] == "["  # v0.1 has no TYPE(); detect lists by their text form
            sum = sum + total(item)
        ELSE
            sum = sum + item
        END
    END
    RETURN sum
END
SAY total([1, [2, [3, [4]]], [], 5])
"""
    assert run(src) == lines(15)


def test_recursion_accumulates_into_shared_list():
    src = """FUNC collect(n, acc)
    IF n == 0
        RETURN acc
    END
    acc[0] = acc[0] + [n]
    RETURN collect(n - 1, acc)
END
LET box = [[]]
collect(4, box)
SAY box[0]
"""
    assert run(src) == "[4, 3, 2, 1]\n"


def test_hanoi_move_count():
    src = """LET moves = [0]
FUNC hanoi(n, a, b, c)
    IF n == 0
        RETURN
    END
    hanoi(n - 1, a, c, b)
    moves[0] = moves[0] + 1
    hanoi(n - 1, c, b, a)
END
hanoi(10, "A", "B", "C")
SAY moves[0]
"""
    assert run(src) == lines(1023)


def deep_recursion(depth):
    return f"""FUNC down(n)
    IF n == 0
        RETURN 0
    END
    RETURN 1 + down(n - 1)
END
SAY down({depth})
"""


def test_recursion_depth_exactly_at_limit_works():
    # down(n) uses n + 1 active calls.
    assert run(deep_recursion(MAX_CALL_DEPTH - 1)) == f"{MAX_CALL_DEPTH - 1}\n"


def test_recursion_depth_over_limit_is_reported():
    src = deep_recursion(MAX_CALL_DEPTH)
    err = assert_fail(src, "RecursionLimitError", at(src, 5, "("), f"maximum call depth of {MAX_CALL_DEPTH}")
    assert len(err.trace) == MAX_CALL_DEPTH + 1  # <main> + every active call
    text = err.format_with_trace()
    assert f"[previous line repeated {MAX_CALL_DEPTH - 1} more times]" in text
    assert len(text.splitlines()) == 5  # header, main, down, repeat note, error


def test_infinite_recursion_is_a_falasz_error_not_a_python_crash():
    src = "FUNC f()\n    RETURN f()\nEND\nf()\n"
    assert_fail(src, "RecursionLimitError", at(src, 2, "("))


def test_infinite_mutual_recursion():
    src = "FUNC a()\n    b()\nEND\nFUNC b()\n    a()\nEND\na()\n"
    err = fail(src)
    assert err.category == "RecursionLimitError"
    assert [e.name for e in err.trace[:4]] == ["<main>", "a", "b", "a"]


def test_call_depth_limit_is_configurable():
    program = parse(deep_recursion(10), "t.falasz")
    assert validate(program) == []
    with pytest.raises(FalaszError) as exc:
        Interpreter("t.falasz", out=io.StringIO(), max_depth=5).run(program)
    assert exc.value.category == "RecursionLimitError"
    out = io.StringIO()
    program = parse(deep_recursion(10), "t.falasz")
    assert validate(program) == []
    Interpreter("t.falasz", out=out, max_depth=11).run(program)
    assert out.getvalue() == "10\n"


def test_deep_recursion_with_heavy_expressions_never_raises_python_recursion_error():
    # Each frame evaluates a deeply nested expression; whichever limit is hit first,
    # the result must be a clean Falasz error or a correct answer.
    nested = "(" * 150 + "n" + " + 0)" * 150
    src = f"""FUNC f(n)
    IF n == 0
        RETURN 0
    END
    RETURN f({nested} - 1) + 1
END
SAY f(400)
"""
    try:
        assert run(src) == "400\n"
    except FalaszError as err:
        assert err.category == "RecursionLimitError"


def test_step_limit_applies_inside_functions():
    src = "FUNC spin()\n    WHILE TRUE\n    END\nEND\nspin()\n"
    with pytest.raises(FalaszError) as exc:
        run(src, max_steps=500)
    assert exc.value.category == "LimitError"


# ================================================================= scopes


def test_parameters_and_locals_are_not_visible_outside():
    src = "FUNC f(p)\n    LET local = 1\nEND\nSAY p\n"
    assert_fail(src, "NameError", at(src, 4, "p"), "'p' is not declared")
    src = "FUNC f(p)\n    LET local = 1\nEND\nf(1)\nSAY local\n"
    assert_fail(src, "NameError", at(src, 5, "local"), "not declared")


def test_parameter_shadows_module_variable():
    src = 'LET x = "module"\nFUNC f(x)\n    x = x + "!"\n    RETURN x\nEND\nSAY f("arg")\nSAY x\n'
    assert run(src) == lines("arg!", "module")


def test_local_let_shadows_module_variable():
    src = 'LET x = "module"\nFUNC f()\n    LET x = "local"\n    RETURN x\nEND\nSAY f()\nSAY x\n'
    assert run(src) == lines("local", "module")


def test_function_reads_and_modifies_module_variable():
    src = "LET counter = 0\nFUNC bump()\n    counter = counter + 1\nEND\nbump()\nbump()\nSAY counter\n"
    assert run(src) == lines(2)


def test_function_sees_current_value_not_value_at_definition():
    src = "LET x = 1\nFUNC get()\n    RETURN x\nEND\nx = 2\nSAY get()\n"
    assert run(src) == lines(2)


def test_function_may_use_module_variable_declared_later_if_it_exists_at_call_time():
    src = "FUNC get()\n    RETURN later\nEND\nLET later = 5\nSAY get()\n"
    assert run(src) == lines(5)


def test_calling_before_later_variable_exists_is_runtime_name_error():
    src = "FUNC get()\n    RETURN later\nEND\nSAY get()\nLET later = 5\n"
    err = assert_fail(src, "NameError", at(src, 2, "later"), "does not exist")
    assert [e.name for e in err.trace] == ["<main>", "get"]


def test_calling_function_before_its_definition_executed():
    src = "SAY f()\nFUNC f()\n    RETURN 1\nEND\n"
    assert_fail(src, "NameError", at(src, 1, "f"), "used before its declaration")
    src = "FUNC g()\n    RETURN f()\nEND\nSAY g()\nFUNC f()\n    RETURN 1\nEND\n"
    assert_fail(src, "NameError", at(src, 2, "f"), "does not exist")


def test_local_from_unexecuted_branch_does_not_leak_to_outer_name():
    src = """LET x = "module"
FUNC f(flag)
    IF flag
        LET x = "local"
    END
    RETURN x
END
SAY f(TRUE)
SAY f(FALSE)
"""
    err = fail(src)
    assert run(src.replace("SAY f(FALSE)\n", "")) == lines("local")
    assert (err.category, tuple(err.pos)) == ("NameError", at(src, 6, "x"))


def test_locals_do_not_survive_between_calls():
    src = """FUNC f(first)
    IF first
        LET memo = "set"
    END
    RETURN memo
END
SAY f(TRUE)
SAY f(FALSE)
"""
    err = fail(src)
    assert err.category == "NameError" and "does not exist" in err.message


def test_closures_counters_are_independent():
    src = """FUNC make_counter()
    LET n = 0
    FUNC inc()
        n = n + 1
        RETURN n
    END
    RETURN inc
END
LET a = make_counter()
LET b = make_counter()
a()
a()
SAY a()
SAY b()
"""
    assert run(src) == lines(3, 1)


def test_closure_keeps_scope_alive_after_return():
    src = """FUNC make_adder(k)
    FUNC add(x)
        RETURN x + k
    END
    RETURN add
END
LET add5 = make_adder(5)
LET add10 = make_adder(10)
SAY add5(1)
SAY add10(1)
SAY make_adder(100)(1)
"""
    assert run(src) == lines(6, 11, 101)


def test_closures_in_loop_share_the_loop_variable():
    # Loops do not create scopes (P6), so every closure sees the same i.
    src = """LET fs = []
FOR i IN [1, 2, 3]
    FUNC show()
        RETURN i
    END
    fs = fs + [show]
END
FOR f IN fs
    SAY f()
END
"""
    assert run(src) == lines(3, 3, 3)


def test_each_func_execution_creates_a_new_function_value():
    src = """LET fs = []
FOR i IN [1, 2]
    FUNC g()
        RETURN 0
    END
    fs = fs + [g]
END
SAY fs[0] == fs[1]
SAY fs[0] == fs[0]
"""
    assert run(src) == lines("FALSE", "TRUE")


def test_three_levels_of_nesting():
    src = """LET a = "A"
FUNC f(b)
    FUNC g(c)
        FUNC h(d)
            a = a + b + c + d
            RETURN a
        END
        RETURN h("d")
    END
    RETURN g("c")
END
SAY f("b")
SAY a
"""
    assert run(src) == lines("Abcd", "Abcd")


def test_function_defined_in_branch_exists_only_if_branch_ran():
    src = "IF FALSE\n    FUNC f()\n    END\nEND\nf()\n"
    assert_fail(src, "NameError", at(src, 5, "f"), "does not exist")
    assert run("IF TRUE\n    FUNC f()\n        RETURN 7\n    END\nEND\nSAY f()\n") == lines(7)


def test_local_declared_later_in_function_hides_outer():
    src = "LET x = 1\nFUNC f()\n    SAY x\n    LET x = 2\nEND\n"
    assert_fail(src, "NameError", at(src, 3, "x"), "used before its declaration")


def test_for_variable_inside_function_is_local():
    src = """LET i = "module"
FUNC f()
    FOR i IN [1, 2]
    END
    RETURN i
END
SAY f()
SAY i
"""
    assert run(src) == lines(2, "module")


def test_redeclaration_rules_inside_functions():
    src = "FUNC f(a)\n    LET a = 1\nEND\n"
    assert_fail(src, "NameError", at(src, 2, "a"), "already declared")
    src = "FUNC f()\n    IF TRUE\n        LET a = 1\n    ELSE\n        LET a = 2\n    END\nEND\n"
    assert_fail(src, "NameError", at(src, 5, "a"), "already declared")


# ============================================================== arguments


def test_parameters_bound_in_order():
    src = 'FUNC f(a, b, c)\n    RETURN STR(a) + STR(b) + STR(c)\nEND\nSAY f(1, "x", TRUE)\n'
    assert run(src) == lines("1xTRUE")


def test_zero_parameters_and_trailing_comma():
    src = "FUNC zero()\n    RETURN 0\nEND\nFUNC two(a, b)\n    RETURN a - b\nEND\nSAY zero()\nSAY two(5, 3,)\n"
    assert run(src) == lines(0, 2)


@pytest.mark.parametrize("call, got", [("f()", 0), ("f(1)", 1), ("f(1, 2, 3)", 3)])
def test_wrong_number_of_arguments(call, got):
    src = f"FUNC f(a, b)\n    RETURN a\nEND\nSAY {call}\n"
    assert_fail(src, "ArityError", at(src, 4, "("), f"f expects 2 argument(s), got {got}")


def test_arity_error_names_function_not_variable():
    src = "FUNC real_name(a)\nEND\nLET alias = real_name\nalias()\n"
    assert_fail(src, "ArityError", at(src, 4, "("), "real_name expects 1")


def test_arguments_evaluated_left_to_right_before_call():
    src = 'FUNC pair(a, b)\n    RETURN a + "," + b\nEND\nSAY pair(INPUT(), INPUT())\n'
    assert run(src, stdin=b"first\nsecond\n") == lines("first,second")


def test_arguments_are_evaluated_even_when_arity_is_wrong():
    src = 'FUNC f(a)\nEND\nf(INPUT("x"), INPUT("y"))\n'
    out = io.StringIO()
    with pytest.raises(FalaszError) as exc:
        run_source(src, "t.falasz", out=out, inp=io.BytesIO(b"1\n2\n"))
    assert exc.value.category == "ArityError" and out.getvalue() == "xy"


def test_argument_error_stops_before_call():
    src = 'FUNC f(a, b)\n    SAY "called"\nEND\nf(1, 1 / 0)\n'
    out = io.StringIO()
    with pytest.raises(FalaszError) as exc:
        run_source(src, "t.falasz", out=out)
    assert exc.value.category == "ZeroDivisionError" and out.getvalue() == ""
    assert exc.value.trace == []  # raised in <main>, not inside f


def test_lists_and_maps_are_passed_by_reference():
    src = """FUNC fill(xs, m)
    xs[0] = "changed"
    m["new"] = 1
END
LET a = ["orig"]
LET b = {}
fill(a, b)
SAY a
SAY b
"""
    assert run(src) == lines('["changed"]', '{"new": 1}')


def test_rebinding_a_parameter_does_not_affect_caller():
    src = """FUNC replace(xs, n)
    xs = [0]
    n = n + 1
END
LET a = [1, 2]
LET k = 5
replace(a, k)
SAY a
SAY k
"""
    assert run(src) == lines("[1, 2]", 5)


def test_same_list_passed_twice_is_one_object():
    src = "FUNC f(a, b)\n    a[0] = 9\n    RETURN b[0]\nEND\nLET xs = [1]\nSAY f(xs, xs)\n"
    assert run(src) == lines(9)


def test_functions_as_arguments_and_return_values():
    src = """FUNC apply(f, x)
    RETURN f(x)
END
FUNC twice(f)
    FUNC g(x)
        RETURN f(f(x))
    END
    RETURN g
END
FUNC inc(x)
    RETURN x + 1
END
SAY apply(inc, 1)
SAY apply(LEN, "abcd")
SAY twice(inc)(5)
SAY twice(twice(inc))(0)
"""
    assert run(src) == lines(2, 4, 7, 4)


def test_user_implemented_map_and_filter():
    src = """FUNC map(f, xs)
    LET out = []
    FOR x IN xs
        out = out + [f(x)]
    END
    RETURN out
END
FUNC filter(keep, xs)
    LET out = []
    FOR x IN xs
        IF keep(x)
            out = out + [x]
        END
    END
    RETURN out
END
FUNC square(x)
    RETURN x * x
END
FUNC is_odd(x)
    RETURN x % 2 == 1
END
SAY map(square, filter(is_odd, RANGE(0, 10)))
SAY map(STR, [1, 2.5, NULL])
"""
    assert run(src) == lines("[1, 9, 25, 49, 81]", '["1", "2.5", "NULL"]')


def test_functions_stored_in_collections():
    src = """FUNC add(a, b)
    RETURN a + b
END
FUNC mul(a, b)
    RETURN a * b
END
LET ops = {"+": add, "*": mul}
LET table = [add, mul]
SAY ops["*"](6, 7)
SAY table[0](1, 2)
SAY ops
"""
    assert run(src) == lines(42, 3, '{"+": <func add>, "*": <func mul>}')


def test_function_values_representation_and_equality():
    src = "FUNC f()\nEND\nLET g = f\nSAY f\nSAY f == g\nSAY f == LEN\nSAY [f] == [g]\nSAY STR(f)\n"
    assert run(src) == lines("<func f>", "TRUE", "FALSE", "TRUE", "<func f>")


@pytest.mark.parametrize("expr", ["f + 1", "f < f", "-f", "f[0]", "NOT f"])
def test_functions_have_no_operators(expr):
    err = fail(f"FUNC f()\nEND\nSAY {expr}\n")
    assert err.category == "TypeError" and "FUNCTION" in err.message


def test_function_cannot_be_used_as_map_key():
    err = fail("FUNC f()\nEND\nLET m = {f: 1}\n")
    assert err.category == "TypeError" and "map keys" in err.message


def test_call_statement_discards_result():
    assert run("FUNC f()\n    SAY \"side\"\n    RETURN 1\nEND\nf()\n") == lines("side")


def test_calling_null_result():
    src = "FUNC f()\nEND\nf()()\n"
    assert_fail(src, "TypeError", at(src, 3, "(", 2), "NULL is not callable")


# =========================================================== call stack


def test_traceback_format():
    src = """FUNC divide(a, b)
    RETURN a / b
END
FUNC mean(xs)
    RETURN divide(0, LEN(xs))
END
SAY mean([])
"""
    err = fail(src)
    assert err.format_with_trace() == "\n".join([
        "Traceback:",
        "  t.falasz:7:9 in <main>",
        "  t.falasz:5:18 in mean",
        "  t.falasz:2:14 in divide",
        "t.falasz:2:14: ZeroDivisionError: division by zero",
    ])


def test_no_traceback_for_errors_in_main():
    err = fail("SAY 1 / 0\n")
    assert err.trace == [] and err.format_with_trace() == err.format()


def test_traceback_through_builtin_call_inside_function():
    src = 'FUNC parse(s)\n    RETURN INT(s)\nEND\nSAY parse("x")\n'
    err = fail(src)
    assert err.category == "ValueError"
    assert [(e.name, tuple(e.pos)) for e in err.trace] == [
        ("<main>", at(src, 4, "(")), ("parse", at(src, 2, "(")),
    ]


def test_traceback_through_higher_order_call():
    src = """FUNC apply(f, x)
    RETURN f(x)
END
FUNC bad(x)
    RETURN x + "s"
END
apply(bad, 1)
"""
    err = fail(src)
    assert [e.name for e in err.trace] == ["<main>", "apply", "bad"]


def test_frames_are_popped_after_errors_and_returns():
    program = parse("FUNC f()\n    RETURN 1\nEND\nf()\nf()\n", "t.falasz")
    validate(program)
    interp = Interpreter("t.falasz", out=io.StringIO())
    interp.run(program)
    assert [f.name for f in interp.frames] == ["<main>"]


def test_python_stack_exhaustion_becomes_falasz_error():
    # With an absurdly high Falasz limit, Python's own stack runs out first; that
    # must still surface as RecursionLimitError, never as a raw RecursionError.
    program = parse("FUNC f(n)\n    RETURN f(n + 1)\nEND\nf(0)\n", "t.falasz")
    assert validate(program) == []
    interp = Interpreter("t.falasz", out=io.StringIO(), max_depth=10**9)
    with pytest.raises(FalaszError) as exc:
        interp.run(program)
    assert exc.value.category == "RecursionLimitError"
    assert "call stack exhausted" in exc.value.message
    assert [f.name for f in interp.frames] == ["<main>"]
