"""Stage 5: modules — relative imports, cycles, namespace isolation, EXPORT."""

import contextlib
import io
import os
import sys

import pytest

from falasz.errors import FalaszError
from falasz.runtime import StaticErrors, check_file, run_file


def write(root, **files):
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8") if isinstance(text, str) else text)
    return root


def run(root, main="main.falasz", stdin=None):
    """Run `falasz run main.falasz` from inside `root`; returns stdout."""
    out = io.StringIO()
    with contextlib.chdir(root):
        run_file(main, out=out, inp=io.BytesIO(stdin) if stdin else None)
    return out.getvalue()


def fail(root, main="main.falasz"):
    out = io.StringIO()
    with contextlib.chdir(root), pytest.raises((FalaszError, StaticErrors)) as exc:
        run_file(main, out=out)
    err = exc.value.errors[0] if isinstance(exc.value, StaticErrors) else exc.value
    return err, out.getvalue()


def where(err):
    return (err.category, err.path, err.pos.line, err.pos.column)


LIB = """EXPORT greet, VERSION
LET VERSION = "1.0"
LET secret = "hidden"
FUNC greet(name)
    RETURN "Hello, " + name
END
"""


# ===================================================== relative imports


def test_import_local_and_plain_import_of_local_file(tmp_path):
    write(tmp_path, **{"lib.falasz": LIB, "main.falasz": 'IMPORT LOCAL lib\nIMPORT lib AS same\nSAY lib.greet("Ala")\nSAY same.VERSION\n'})
    assert run(tmp_path) == "Hello, Ala\n1.0\n"


def test_imports_resolve_against_importing_file_not_cwd(tmp_path):
    project = write(tmp_path / "project", **{"lib.falasz": LIB, "main.falasz": "IMPORT LOCAL lib\nSAY lib.VERSION\n"})
    # A decoy module in the current directory must be ignored.
    write(tmp_path / "elsewhere", **{"lib.falasz": 'EXPORT VERSION\nLET VERSION = "decoy"\n'})
    out = io.StringIO()
    with contextlib.chdir(tmp_path / "elsewhere"):
        run_file(str(project / "main.falasz"), out=out)
        run_file(os.path.join("..", "project", "main.falasz"), out=out)
    assert out.getvalue() == "1.0\n1.0\n"


def test_chain_of_imports(tmp_path):
    write(tmp_path, **{
        "c.falasz": "EXPORT z\nLET z = 3\n",
        "b.falasz": "EXPORT y\nIMPORT LOCAL c\nLET y = c.z * 2\n",
        "a.falasz": "EXPORT x\nIMPORT LOCAL b\nLET x = b.y + 1\n",
        "main.falasz": "IMPORT LOCAL a\nSAY a.x\n",
    })
    assert run(tmp_path) == "7\n"


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges on Windows")
def test_symlinked_main_imports_relative_to_real_file(tmp_path):
    write(tmp_path / "real", **{"lib.falasz": LIB, "main.falasz": "IMPORT LOCAL lib\nSAY lib.VERSION\n"})
    (tmp_path / "link").mkdir()
    os.symlink(tmp_path / "real" / "main.falasz", tmp_path / "link" / "main.falasz")
    assert run(tmp_path / "link") == "1.0\n"


@pytest.mark.parametrize("line", ["IMPORT ../lib", "IMPORT lib.falasz", 'IMPORT "lib"', "IMPORT LOCAL dir/lib"])
def test_import_cannot_contain_a_path(tmp_path, line):
    write(tmp_path, **{"lib.falasz": LIB, "main.falasz": line + "\n"})
    err, _ = fail(tmp_path)
    assert err.category == "SyntaxError"


def test_python_files_are_never_imported(tmp_path):
    write(tmp_path, **{"helper.py": "raise SystemExit('python code ran')\n", "main.falasz": "IMPORT helper\n"})
    err, _ = fail(tmp_path)
    assert where(err) == ("ImportError", "main.falasz", 1, 1)
    assert "cannot find module 'helper'" in err.message


def test_directory_with_module_name_is_not_a_module(tmp_path):
    (tmp_path / "lib.falasz").mkdir()
    write(tmp_path, **{"main.falasz": "IMPORT LOCAL lib\n"})
    err, _ = fail(tmp_path)
    assert err.category == "ImportError"


def test_module_name_case_must_match_exactly(tmp_path):
    write(tmp_path, **{"Lib.falasz": LIB, "main.falasz": "IMPORT LOCAL lib\n"})
    err, _ = fail(tmp_path)
    assert where(err) == ("ImportError", "main.falasz", 1, 1)
    write(tmp_path, **{"main.falasz": "IMPORT LOCAL Lib\nSAY Lib.VERSION\n"})
    assert run(tmp_path) == "1.0\n"


@pytest.mark.parametrize("name", ["con", "CON", "nul", "Com1", "lpt9", "aux", "prn"])
def test_windows_reserved_module_names_are_rejected_everywhere(tmp_path, name):
    if sys.platform != "win32":
        write(tmp_path, **{f"{name}.falasz": "LET x = 1\n"})
    write(tmp_path, **{"main.falasz": f"IMPORT LOCAL {name}\n"})
    err, _ = fail(tmp_path)
    assert err.category == "ImportError" and "reserved device name" in err.message


def test_missing_module_messages(tmp_path):
    write(tmp_path, **{"main.falasz": "IMPORT LOCAL nope\nIMPORT nada\n"})
    with contextlib.chdir(tmp_path):
        result = check_file("main.falasz")
    assert [e.format() for e in result.errors] == [
        "main.falasz:1:1: ImportError: cannot find module 'nope' (looked in nope.falasz)",
        "main.falasz:2:1: ImportError: cannot find module 'nada' (looked in the standard library and nada.falasz)",
    ]


def test_errors_in_module_are_reported_with_module_path(tmp_path):
    write(tmp_path, **{"lib.falasz": "EXPORT f\nFUNC f()\n    RETURN 1 +\nEND\n", "main.falasz": "IMPORT LOCAL lib\nSAY lib.whatever\nSAY nope\n"})
    with contextlib.chdir(tmp_path):
        result = check_file("main.falasz")
    # The module's syntax error, and main's own error; lib.whatever cannot be
    # checked because lib's exports are unknown.
    assert [(e.category, e.path, tuple(e.pos)) for e in result.errors] == [
        ("NameError", "main.falasz", (3, 5)),
        ("SyntaxError", "lib.falasz", (3, 15)),
    ]


def test_module_with_invalid_utf8(tmp_path):
    write(tmp_path, **{"lib.falasz": b"LET x = \"\xff\"\n", "main.falasz": "IMPORT LOCAL lib\n"})
    err, _ = fail(tmp_path)
    assert where(err) == ("SyntaxError", "lib.falasz", 1, 10)


@pytest.mark.skipif(sys.platform == "win32" or os.geteuid() == 0, reason="needs POSIX permissions, non-root")
def test_unreadable_module(tmp_path):
    write(tmp_path, **{"lib.falasz": LIB, "main.falasz": "IMPORT LOCAL lib\n"})
    os.chmod(tmp_path / "lib.falasz", 0)
    try:
        err, _ = fail(tmp_path)
    finally:
        os.chmod(tmp_path / "lib.falasz", 0o644)
    assert err.category == "ImportError" and err.path == "lib.falasz"


# ================================================================ cycles


def test_self_import_is_a_cycle(tmp_path):
    write(tmp_path, **{"main.falasz": "IMPORT LOCAL main\n"})
    err, _ = fail(tmp_path)
    assert where(err) == ("ImportError", "main.falasz", 1, 1)
    assert err.message == "import cycle: main.falasz -> main.falasz"


def test_two_module_cycle(tmp_path):
    write(tmp_path, **{
        "main.falasz": 'SAY "never printed"\nIMPORT LOCAL a\n',
        "a.falasz": "IMPORT LOCAL b\n",
        "b.falasz": "LET x = 1\nIMPORT LOCAL a\n",
    })
    err, out = fail(tmp_path)
    assert where(err) == ("ImportError", "b.falasz", 2, 1)
    assert err.message == "import cycle: a.falasz -> b.falasz -> a.falasz"
    assert out == ""  # detected statically, before anything runs


def test_three_module_cycle_through_main(tmp_path):
    write(tmp_path, **{
        "main.falasz": "IMPORT LOCAL a\n",
        "a.falasz": "IMPORT b\n",
        "b.falasz": "IMPORT LOCAL main AS m\n",
    })
    err, _ = fail(tmp_path)
    assert err.message == "import cycle: main.falasz -> a.falasz -> b.falasz -> main.falasz"
    assert (err.path, tuple(err.pos)) == ("b.falasz", (1, 1))


def test_cycle_found_by_check_without_executing(tmp_path, capsys):
    write(tmp_path, **{"main.falasz": 'SAY "x"\nIMPORT LOCAL a\n', "a.falasz": 'SAY "y"\nIMPORT LOCAL main\n'})
    with contextlib.chdir(tmp_path):
        result = check_file("main.falasz")
    assert [e.category for e in result.errors] == ["ImportError"]
    assert capsys.readouterr().out == ""


def test_diamond_is_not_a_cycle_and_shared_module_runs_once(tmp_path):
    write(tmp_path, **{
        "base.falasz": 'EXPORT n\nSAY "base runs"\nLET n = 1\n',
        "left.falasz": "EXPORT v\nIMPORT LOCAL base\nLET v = base.n + 10\n",
        "right.falasz": "EXPORT v\nIMPORT LOCAL base\nLET v = base.n + 20\n",
        "main.falasz": "IMPORT LOCAL left\nIMPORT LOCAL right\nIMPORT LOCAL base\nSAY left.v + right.v + base.n\n",
    })
    assert run(tmp_path) == "base runs\n33\n"  # 11 + 21 + 1


# ==================================================== namespace isolation


def test_private_names_are_not_accessible(tmp_path):
    write(tmp_path, **{"lib.falasz": LIB, "main.falasz": "IMPORT LOCAL lib\nSAY lib.secret\n"})
    err, _ = fail(tmp_path)
    assert where(err) == ("NameError", "main.falasz", 2, 8)
    assert err.message == "module 'lib' does not export 'secret'"


def test_private_names_not_accessible_through_another_variable(tmp_path):
    write(tmp_path, **{"lib.falasz": LIB, "main.falasz": "IMPORT LOCAL lib\nLET alias = lib\nSAY alias.secret\n"})
    err, _ = fail(tmp_path)
    assert where(err) == ("NameError", "main.falasz", 3, 10)


def test_module_does_not_see_importer_names(tmp_path):
    write(tmp_path, **{
        "lib.falasz": "EXPORT f\nFUNC f()\n    RETURN shared\nEND\n",
        "main.falasz": "LET shared = 1\nIMPORT LOCAL lib\nSAY lib.f()\n",
    })
    err, _ = fail(tmp_path)
    assert where(err) == ("NameError", "lib.falasz", 3, 12)


def test_same_names_in_different_modules_are_independent(tmp_path):
    write(tmp_path, **{
        "a.falasz": 'EXPORT name, get\nLET name = "a"\nFUNC get()\n    RETURN name\nEND\n',
        "b.falasz": 'EXPORT name, get\nLET name = "b"\nFUNC get()\n    RETURN name\nEND\n',
        "main.falasz": 'IMPORT LOCAL a\nIMPORT LOCAL b\nLET name = "main"\nSAY a.get() + b.get() + name + a.name + b.name\n',
    })
    assert run(tmp_path) == "abmainab\n"


def test_exported_variables_are_live_bindings(tmp_path):
    write(tmp_path, **{
        "counter.falasz": "EXPORT count, bump\nLET count = 0\nFUNC bump()\n    count = count + 1\nEND\n",
        "main.falasz": "IMPORT LOCAL counter\ncounter.bump()\ncounter.bump()\nSAY counter.count\n",
    })
    assert run(tmp_path) == "2\n"


def test_module_members_are_read_only(tmp_path):
    write(tmp_path, **{"lib.falasz": LIB, "main.falasz": 'IMPORT LOCAL lib\nlib.VERSION = "2"\n'})
    err, _ = fail(tmp_path)
    assert where(err) == ("NameError", "main.falasz", 2, 4)
    assert "read-only" in err.message


def test_rebinding_import_name_does_not_change_module(tmp_path):
    write(tmp_path, **{"lib.falasz": LIB, "main.falasz": "IMPORT LOCAL lib\nIMPORT LOCAL lib AS keep\nlib = 5\nSAY lib\nSAY keep.VERSION\n"})
    assert run(tmp_path) == "5\n1.0\n"


def test_exported_mutable_values_are_shared_references(tmp_path):
    write(tmp_path, **{
        "store.falasz": "EXPORT items, first\nLET items = [1]\nFUNC first()\n    RETURN items[0]\nEND\n",
        "main.falasz": "IMPORT LOCAL store\nLET xs = store.items\nxs[0] = 99\nSAY store.first()\n",
    })
    assert run(tmp_path) == "99\n"


def test_module_runs_once_at_first_import_point(tmp_path):
    write(tmp_path, **{
        "noisy.falasz": 'EXPORT x\nSAY "noisy loaded"\nLET x = 1\n',
        "main.falasz": 'SAY "start"\nIMPORT LOCAL noisy\nSAY "middle"\nIMPORT LOCAL noisy AS again\nSAY noisy == again\n',
    })
    assert run(tmp_path) == "start\nnoisy loaded\nmiddle\nTRUE\n"


def test_module_values(tmp_path):
    write(tmp_path, **{"lib.falasz": LIB, "main.falasz": "IMPORT LOCAL lib\nIMPORT files\nSAY lib\nSAY files\nSAY [lib]\nSAY lib == files\n"})
    assert run(tmp_path) == "<module lib>\n<module files>\n[<module lib>]\nFALSE\n"


@pytest.mark.parametrize("expr, category", [
    ("lib()", "TypeError"), ("lib[0]", "TypeError"), ("{lib: 1}", "TypeError"),
    ("lib + 1", "TypeError"), ("LEN(lib)", "TypeError"),
])
def test_module_value_misuse(tmp_path, expr, category):
    write(tmp_path, **{"lib.falasz": LIB, "main.falasz": f"IMPORT LOCAL lib\nSAY {expr}\n"})
    err, _ = fail(tmp_path)
    assert err.category == category


def test_member_access_on_non_module(tmp_path):
    write(tmp_path, **{"main.falasz": "LET m = {}\nSAY m.x\n"})
    err, _ = fail(tmp_path)
    assert where(err) == ("TypeError", "main.falasz", 2, 6)


def test_exported_variable_whose_declaration_did_not_run(tmp_path):
    write(tmp_path, **{
        "lib.falasz": "EXPORT maybe\nIF FALSE\n    LET maybe = 1\nEND\n",
        "main.falasz": "IMPORT LOCAL lib\nSAY lib.maybe\n",
    })
    err, _ = fail(tmp_path)
    assert where(err) == ("NameError", "main.falasz", 2, 8)
    assert "does not exist" in err.message


def test_re_export_of_an_import(tmp_path):
    write(tmp_path, **{
        "data.txt": "payload",
        "io_tools.falasz": "EXPORT files\nIMPORT files\n",
        "main.falasz": 'IMPORT LOCAL io_tools\nSAY io_tools.files.read_text("data.txt")\n',
    })
    assert run(tmp_path) == "payload\n"


def test_export_in_main_script_is_allowed(tmp_path):
    write(tmp_path, **{"main.falasz": "EXPORT x\nLET x = 1\nSAY x\n"})
    assert run(tmp_path) == "1\n"


def test_export_errors(tmp_path):
    write(tmp_path, **{"lib.falasz": "EXPORT a, a\nEXPORT missing\nLET a = 1\n", "main.falasz": "IMPORT LOCAL lib\n"})
    with contextlib.chdir(tmp_path):
        result = check_file("main.falasz")
    assert [(e.path, tuple(e.pos), e.message.split(":")[0]) for e in result.errors] == [
        ("lib.falasz", (1, 11), "'a' is already exported (line 1)"),
        ("lib.falasz", (2, 8), "cannot export 'missing'"),
    ]


def test_error_in_module_top_level_has_traceback(tmp_path):
    write(tmp_path, **{"lib.falasz": "EXPORT x\nLET x = 1 / 0\n", "main.falasz": "IMPORT LOCAL lib\n"})
    err, _ = fail(tmp_path)
    assert err.format_with_trace() == "\n".join([
        "Traceback:",
        "  main.falasz:1:1 in <main>",
        "  lib.falasz:2:11 in <module lib>",
        "lib.falasz:2:11: ZeroDivisionError: division by zero",
    ])


def test_error_in_module_function_is_reported_in_module_file(tmp_path):
    write(tmp_path, **{
        "lib.falasz": 'EXPORT parse\nFUNC parse(s)\n    RETURN INT(s)\nEND\n',
        "main.falasz": 'IMPORT LOCAL lib\nSAY lib.parse("x")\n',
    })
    err, _ = fail(tmp_path)
    assert where(err) == ("ValueError", "lib.falasz", 3, 15)
    assert [(e.path, e.name) for e in err.trace] == [("main.falasz", "<main>"), ("lib.falasz", "parse")]


def test_stdlib_shadow_warning(tmp_path):
    write(tmp_path, **{"files.falasz": "EXPORT hello\nFUNC hello()\nEND\n", "main.falasz": "IMPORT files\nIMPORT LOCAL files AS mine\n"})
    with contextlib.chdir(tmp_path):
        result = check_file("main.falasz")
    assert result.errors == []
    assert [w.format() for w in result.warnings] == [
        "main.falasz:1:1: Warning: 'IMPORT files' uses the standard library module; the local file "
        "files.falasz is ignored (use 'IMPORT LOCAL files AS ...' to import it)",
    ]


def test_no_warning_without_local_shadow(tmp_path):
    write(tmp_path, **{"main.falasz": "IMPORT files\n"})
    with contextlib.chdir(tmp_path):
        assert check_file("main.falasz").warnings == []


def test_unknown_stdlib_member_is_static_error(tmp_path):
    write(tmp_path, **{"main.falasz": 'IMPORT files\nfiles.delete("x")\n'})
    err, _ = fail(tmp_path)
    assert where(err) == ("NameError", "main.falasz", 2, 6)
    assert err.message == "module 'files' does not export 'delete'"


def test_local_name_shadowing_import_is_not_member_checked(tmp_path):
    write(tmp_path, **{"lib.falasz": LIB, "main.falasz": "IMPORT LOCAL lib\nFUNC f(lib)\n    RETURN lib.anything\nEND\n"})
    with contextlib.chdir(tmp_path):
        assert check_file("main.falasz").errors == []


def test_sensors_module_is_stage_6(tmp_path):
    write(tmp_path, **{"main.falasz": "IMPORT sensors\nSAY sensors.available()\n"})
    err, _ = fail(tmp_path)
    assert err.category == "NotImplementedError"


def test_check_does_not_execute_modules(tmp_path, capsys):
    write(tmp_path, **{"lib.falasz": 'SAY "side effect"\nLET x = INPUT()\n', "main.falasz": "IMPORT LOCAL lib\n"})
    with contextlib.chdir(tmp_path):
        assert check_file("main.falasz").errors == []
    assert capsys.readouterr().out == ""
