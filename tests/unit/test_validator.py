import pytest

from falasz import nodes as n
from falasz.parser import parse
from falasz.validator import validate


def errors(src):
    return [(e.category, e.pos.line, e.pos.column, e.message) for e in validate(parse(src, "t.falasz"))]


def assert_ok(src):
    assert errors(src) == []


def assert_error(src, line, col, fragment):
    errs = errors(src)
    assert errs, "expected an error"
    category, l, c, message = errs[0]
    assert (category, l, c) == ("NameError", line, col), errs
    assert fragment in message, message


# ------------------------------------------------------------ declarations


def test_declared_names_ok():
    assert_ok("LET a = 1\nSAY a\na = 2\nFOR i IN [1]\n SAY i\nEND\nSAY i\n")


def test_undeclared_read_and_assign():
    assert_error("SAY a\n", 1, 5, "'a' is not declared")
    assert_error("a = 1\n", 1, 1, "'a' is not declared")
    assert_error("LET xs = []\nys[0] = 1\n", 2, 1, "'ys' is not declared")


def test_use_before_declaration():
    assert_error("SAY a\nLET a = 1\n", 1, 5, "used before its declaration (line 2)")
    assert_error("a = 1\nLET a = 2\n", 1, 1, "used before its declaration")


def test_let_initializer_cannot_use_itself():
    assert_error("LET x = x + 1\n", 1, 9, "used before its declaration")


def test_use_before_declaration_in_loop_body_order():
    assert_error("WHILE TRUE\n SAY t\n LET t = 1\nEND\n", 2, 6, "used before")


def test_for_iterable_evaluated_before_variable_exists():
    assert_error("FOR x IN x\nEND\n", 1, 10, "used before")


def test_redeclaration_same_scope():
    assert_error("LET a = 1\nLET a = 2\n", 2, 5, "already declared in this scope (line 1)")


def test_redeclaration_across_if_branches_and_blocks():
    assert_error("IF TRUE\n LET a = 1\nELSE\n LET a = 2\nEND\n", 4, 6, "already declared")
    assert_error("LET a = 1\nWHILE FALSE\n LET a = 2\nEND\n", 3, 6, "already declared")


def test_blocks_do_not_create_scopes():
    assert_ok("IF TRUE\n LET a = 1\nEND\nSAY a\nWHILE FALSE\n LET b = 2\nEND\nSAY b\n")


def test_let_in_loop_is_one_declaration():
    assert_ok("FOR i IN [1, 2]\n LET sq = i * i\nEND\n")


def test_for_variable_may_be_shared_by_loops():
    assert_ok("FOR i IN [1]\nEND\nFOR i IN [2]\nEND\nFOR i IN [3]\n FOR j IN [4]\n END\nEND\n")


def test_for_variable_conflicts_with_other_declarations():
    assert_error("LET i = 0\nFOR i IN [1]\nEND\n", 2, 5, "already declared")
    assert_error("FOR i IN [1]\nEND\nLET i = 0\n", 3, 5, "already declared")
    assert_error("FUNC i()\nEND\nFOR i IN [1]\nEND\n", 3, 5, "already declared")


def test_func_and_let_conflict():
    assert_error("FUNC f()\nEND\nLET f = 1\n", 3, 5, "already declared")


def test_import_binding_conflicts():
    assert_error("IMPORT files\nIMPORT LOCAL files\n", 2, 14, "already declared")
    assert_error("LET files = 1\nIMPORT files\n", 2, 8, "already declared")
    assert_ok("IMPORT files\nIMPORT LOCAL files AS my_files\n")


@pytest.mark.parametrize("src, col", [
    ("LET LEN = 1\n", 5),
    ("FUNC STR()\nEND\n", 6),
    ("FOR INT IN [1]\nEND\n", 5),
    ("IMPORT files AS RANGE\n", 17),
    ("FUNC f(INPUT)\nEND\n", 8),
])
def test_builtin_names_cannot_be_declared(src, col):
    assert_error(src, 1, col, "builtin name")


def test_builtin_names_cannot_be_assigned():
    assert_error("FLOAT = 1\n", 1, 1, "cannot assign to builtin 'FLOAT'")


def test_builtins_resolve():
    prog = parse("SAY LEN\n")
    validate(prog)
    assert prog.body[0].value.hops == n.BUILTIN


def test_keywords_are_case_sensitive_so_lowercase_names_are_ordinary():
    assert_ok("LET len = 1\nLET range = 2\nLET if = 3\nSAY len + range + if\n")


# ------------------------------------------------------------------ functions


def test_function_scope_and_params():
    assert_ok("FUNC f(a, b)\n LET c = a + b\n RETURN c\nEND\n")
    assert_error("FUNC f()\n LET c = 1\nEND\nSAY c\n", 4, 5, "'c' is not declared")


def test_param_and_local_conflict():
    assert_error("FUNC f(a)\n LET a = 1\nEND\n", 2, 6, "already declared")


def test_function_may_shadow_outer_names():
    assert_ok("LET x = 1\nFUNC f(x)\n RETURN x\nEND\nFUNC g()\n LET x = 2\n RETURN x\nEND\n")


def test_function_sees_later_outer_declarations():
    assert_ok("FUNC f()\n RETURN g() + later\nEND\nFUNC g()\n RETURN 1\nEND\nLET later = 2\n")


def test_local_declared_later_hides_outer_name():
    # x inside f refers to f's own (later) x, so this is a use before declaration.
    assert_error("LET x = 1\nFUNC f()\n SAY x\n LET x = 2\nEND\n", 3, 6, "used before")


def test_recursion_and_nested_functions():
    assert_ok("FUNC f(n)\n FUNC g()\n  RETURN f(n - 1) + n\n END\n RETURN g\nEND\n")


def test_hops_annotation():
    prog = parse("LET a = 1\nFUNC f(b)\n FUNC g()\n  RETURN a + b\n END\n RETURN g\nEND\n")
    assert validate(prog) == []
    ret = prog.body[1].body[0].body[0]
    assert (ret.value.left.hops, ret.value.right.hops) == (2, 1)


def test_closure_assignment_resolves_outer_variable():
    prog = parse("FUNC counter()\n LET n = 0\n FUNC inc()\n  n = n + 1\n END\n RETURN inc\nEND\n")
    assert validate(prog) == []
    assign = prog.body[0].body[1].body[0]
    assert assign.target.hops == 1


# -------------------------------------------------------------------- exports


def test_exports():
    assert_ok("EXPORT f, x, files, i\nFUNC f()\nEND\nLET x = 1\nIMPORT files\nFOR i IN []\nEND\n")
    assert_error("EXPORT missing\n", 1, 8, "cannot export 'missing'")
    assert_error("EXPORT a\nEXPORT a\nLET a = 1\n", 2, 8, "already exported")


def test_cannot_export_function_local():
    assert_error("EXPORT c\nFUNC f()\n LET c = 1\nEND\n", 1, 8, "cannot export 'c'")


# ------------------------------------------------------------- error report


def test_all_errors_collected_in_source_order():
    errs = errors("SAY a\nSAY b\nLET c = 1\nLET c = 2\n")
    assert [(l, c) for _, l, c, _ in errs] == [(1, 5), (2, 5), (4, 5)]
