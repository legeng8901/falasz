"""Stage 7: the `falasz` command line (spec 11.3-11.4).

Most tests start a real process (`python -m falasz ...`) to check the exact bytes
on stdout/stderr and the exit codes, including UTF-8 and LF line endings.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import falasz
from falasz import cli

EXAMPLES = Path(__file__).parent.parent / "examples"


def falasz_cmd(*args, cwd=None, stdin=b"", env=None):
    proc = subprocess.run(
        [sys.executable, "-m", "falasz", *args],
        cwd=cwd, input=stdin, capture_output=True, timeout=60,
        env={**os.environ, **(env or {})},
    )
    return proc.returncode, proc.stdout, proc.stderr.decode("utf-8")


def write(root, name, text):
    path = root / name
    path.write_bytes(text.encode("utf-8") if isinstance(text, str) else text)
    return path


# ============================================================== version


def test_version():
    code, out, err = falasz_cmd("--version")
    assert (code, out, err) == (0, f"falasz {falasz.__version__}\n".encode(), "")
    assert falasz.__version__ == "0.1.0a0"


def test_help():
    code, out, _ = falasz_cmd("--help")
    assert code == 0 and b"run" in out and b"check" in out


def test_run_help_mentions_options():
    code, out, _ = falasz_cmd("run", "--help")
    assert code == 0 and b"--sensors-mock" in out and b"--max-steps" in out


# ================================================================== run


def test_run_success_output_is_utf8_with_lf(tmp_path):
    write(tmp_path, "p.falasz", 'SAY "zażółć 🙂"\nSAY [1, "a"]\n')
    code, out, err = falasz_cmd("run", "p.falasz", cwd=tmp_path)
    assert (code, err) == (0, "")
    assert out == "zażółć 🙂\n[1, \"a\"]\n".encode("utf-8")  # no \r\n, even on Windows


def test_run_from_other_directory_reports_path_as_given(tmp_path):
    (tmp_path / "proj").mkdir()
    write(tmp_path / "proj", "p.falasz", "SAY 1 / 0\n")
    code, out, err = falasz_cmd("run", os.path.join("proj", "p.falasz"), cwd=tmp_path)
    assert code == 1
    assert err == f"{os.path.join('proj', 'p.falasz')}:1:7: ZeroDivisionError: division by zero\n"


def test_runtime_error_exit_1_with_traceback_on_stderr(tmp_path):
    write(tmp_path, "p.falasz", 'SAY "before"\nFUNC f()\n    RETURN 1 / 0\nEND\nf()\n')
    code, out, err = falasz_cmd("run", "p.falasz", cwd=tmp_path)
    assert code == 1
    assert out == b"before\n"  # output produced before the error is kept
    assert err == ("Traceback:\n  p.falasz:5:2 in <main>\n  p.falasz:3:14 in f\n"
                   "p.falasz:3:14: ZeroDivisionError: division by zero\n")


def test_static_errors_exit_3_and_nothing_runs(tmp_path):
    write(tmp_path, "p.falasz", 'SAY "never"\nSAY a\nSAY b\n')
    code, out, err = falasz_cmd("run", "p.falasz", cwd=tmp_path)
    assert (code, out) == (3, b"")
    assert err == "p.falasz:2:5: NameError: 'a' is not declared\np.falasz:3:5: NameError: 'b' is not declared\n"


def test_syntax_error_exit_3(tmp_path):
    write(tmp_path, "p.falasz", "IF TRUE\n")
    code, _, err = falasz_cmd("run", "p.falasz", cwd=tmp_path)
    assert code == 3 and err.startswith("p.falasz:2:1: SyntaxError:")


def test_import_error_exit_3(tmp_path):
    write(tmp_path, "p.falasz", "IMPORT LOCAL nothing\n")
    code, _, err = falasz_cmd("run", "p.falasz", cwd=tmp_path)
    assert code == 3 and "ImportError" in err


def test_input_reads_stdin_as_utf8(tmp_path):
    write(tmp_path, "p.falasz", 'LET n = INPUT("Name: ")\nSAY "Hi " + n + " " + STR(LEN(n))\nSAY INPUT()\n')
    code, out, _ = falasz_cmd("run", "p.falasz", cwd=tmp_path, stdin="Łucja\r\n".encode("utf-8"))
    assert (code, out) == (0, "Name: Hi Łucja 5\nNULL\n".encode("utf-8"))


def test_input_with_closed_stdin(tmp_path):
    write(tmp_path, "p.falasz", "SAY INPUT()\n")
    proc = subprocess.run([sys.executable, "-m", "falasz", "run", "p.falasz"], cwd=tmp_path,
                          stdin=subprocess.DEVNULL, capture_output=True, timeout=60)
    assert (proc.returncode, proc.stdout) == (0, b"NULL\n")


def test_files_relative_to_script_not_cwd(tmp_path):
    (tmp_path / "proj").mkdir()
    write(tmp_path / "proj", "data.txt", "inside")
    write(tmp_path / "proj", "p.falasz", 'IMPORT files\nSAY files.read_text("data.txt")\n')
    code, out, _ = falasz_cmd("run", str(tmp_path / "proj" / "p.falasz"), cwd=tmp_path)
    assert (code, out) == (0, b"inside\n")


def test_warnings_go_to_stderr_and_do_not_change_exit_code(tmp_path):
    write(tmp_path, "files.falasz", "LET x = 1\n")
    write(tmp_path, "p.falasz", "IMPORT files\nSAY 1\n")
    code, out, err = falasz_cmd("run", "p.falasz", cwd=tmp_path)
    assert (code, out) == (0, b"1\n")
    assert err.startswith("p.falasz:1:1: Warning: 'IMPORT files' uses the standard library module")


# ========================================================== run options


def test_sensors_mock(tmp_path):
    write(tmp_path, "s.json", json.dumps({"t": [1.5, 2.5], "name": "lab"}))
    write(tmp_path, "p.falasz", 'IMPORT sensors\nSAY sensors.available()\nSAY sensors.read("t") + sensors.read("t")\n')
    code, out, err = falasz_cmd("run", "--sensors-mock", "s.json", "p.falasz", cwd=tmp_path)
    assert (code, out, err) == (0, b'["name", "t"]\n4.0\n', "")


def test_without_sensors_mock_there_are_no_sensors(tmp_path):
    write(tmp_path, "p.falasz", 'IMPORT sensors\nSAY sensors.available()\nSAY sensors.read("t")\n')
    code, out, err = falasz_cmd("run", "p.falasz", cwd=tmp_path)
    assert (code, out) == (1, b"[]\n")
    assert "SensorError" in err


@pytest.mark.parametrize("content, fragment", [
    ('{"a": null}', "sensor 'a'"),
    ("{bad json", "invalid JSON"),
])
def test_invalid_sensors_mock_is_usage_error_before_running(tmp_path, content, fragment):
    write(tmp_path, "s.json", content)
    write(tmp_path, "p.falasz", 'SAY "never"\n')
    code, out, err = falasz_cmd("run", "--sensors-mock", "s.json", "p.falasz", cwd=tmp_path)
    assert (code, out) == (2, b"")
    assert err.startswith("falasz: error: invalid --sensors-mock data:") and fragment in err


def test_missing_sensors_mock_file(tmp_path):
    write(tmp_path, "p.falasz", "SAY 1\n")
    code, _, err = falasz_cmd("run", "--sensors-mock", "nope.json", "p.falasz", cwd=tmp_path)
    assert code == 2 and "cannot read sensor mock file" in err


def test_max_steps(tmp_path):
    write(tmp_path, "p.falasz", "LET i = 0\nWHILE TRUE\n    i = i + 1\nEND\n")
    code, out, err = falasz_cmd("run", "--max-steps", "1000", "p.falasz", cwd=tmp_path)
    assert code == 1 and "LimitError: step limit of 1000 exceeded" in err


@pytest.mark.parametrize("value", ["0", "-5", "abc", "1.5"])
def test_max_steps_must_be_positive_integer(tmp_path, value):
    write(tmp_path, "p.falasz", "SAY 1\n")
    code, _, err = falasz_cmd("run", "--max-steps", value, "p.falasz", cwd=tmp_path)
    assert code == 2 and "--max-steps" in err


# ================================================================ check


def test_check_ok(tmp_path):
    write(tmp_path, "p.falasz", 'SAY "not printed by check"\nLET x = INPUT()\n')
    code, out, err = falasz_cmd("check", "p.falasz", cwd=tmp_path)
    assert (code, out, err) == (0, b"OK\n", "")


def test_check_reports_all_errors_and_never_runs(tmp_path):
    write(tmp_path, "lib.falasz", "EXPORT a\nLET a = b\n")
    write(tmp_path, "p.falasz", 'SAY "x"\nIMPORT LOCAL lib\nSAY lib.zzz\nSAY missing\n')
    code, out, err = falasz_cmd("check", "p.falasz", cwd=tmp_path)
    assert (code, out) == (3, b"")
    assert err == ("p.falasz:3:8: NameError: module 'lib' does not export 'zzz'\n"
                   "p.falasz:4:5: NameError: 'missing' is not declared\n"
                   "lib.falasz:2:9: NameError: 'b' is not declared\n"
                   "3 errors found\n")


def test_check_does_not_need_sensor_data_or_input(tmp_path):
    write(tmp_path, "p.falasz", 'IMPORT sensors\nSAY sensors.read("t")\nSAY INPUT()\n')
    code, out, _ = falasz_cmd("check", "p.falasz", cwd=tmp_path)
    assert (code, out) == (0, b"OK\n")


def test_check_single_error_message(tmp_path):
    write(tmp_path, "p.falasz", "SAY 1 +\n")
    code, _, err = falasz_cmd("check", "p.falasz", cwd=tmp_path)
    assert code == 3 and err.endswith("\n1 error found\n")


def test_check_shows_warnings(tmp_path):
    write(tmp_path, "files.falasz", "LET x = 1\n")
    write(tmp_path, "p.falasz", "IMPORT files\n")
    code, out, err = falasz_cmd("check", "p.falasz", cwd=tmp_path)
    assert (code, out) == (0, b"OK\n") and "Warning" in err


# ========================================================== usage errors


@pytest.mark.parametrize("args", [[], ["frobnicate"], ["run"], ["check"], ["run", "a", "b"]])
def test_usage_errors_exit_2(args):
    code, out, err = falasz_cmd(*args)
    assert code == 2 and out == b"" and "usage: falasz" in err


@pytest.mark.parametrize("command", ["run", "check"])
def test_missing_input_file_exit_2(tmp_path, command):
    code, _, err = falasz_cmd(command, "nope.falasz", cwd=tmp_path)
    assert code == 2 and err == "falasz: error: cannot open 'nope.falasz': no such file\n"


def test_directory_as_input_exit_2(tmp_path):
    (tmp_path / "d.falasz").mkdir()
    code, _, err = falasz_cmd("run", "d.falasz", cwd=tmp_path)
    assert code == 2 and "is a directory" in err


def test_non_utf8_source_is_syntax_error(tmp_path):
    write(tmp_path, "p.falasz", b"SAY \"\xff\"\n")
    code, _, err = falasz_cmd("run", "p.falasz", cwd=tmp_path)
    assert code == 3 and err.startswith("p.falasz:1:6: SyntaxError: invalid UTF-8")


def test_crlf_source_file_runs_identically(tmp_path):
    write(tmp_path, "p.falasz", b"LET a = 1\r\nIF a == 1\r\n    SAY \"ok\"\r\nEND\r\nSAY 1 / 0\r\n")
    code, out, err = falasz_cmd("run", "p.falasz", cwd=tmp_path)
    assert (code, out) == (1, b"ok\n") and err.startswith("p.falasz:5:7:")


# ======================================================== internal errors


def test_internal_error_exit_70(tmp_path, monkeypatch, capsys):
    write(tmp_path, "p.falasz", "SAY 1\n")

    def boom(*args, **kwargs):
        raise RuntimeError("simulated bug")

    monkeypatch.setattr(cli, "run_file", boom)
    assert cli.main(["run", str(tmp_path / "p.falasz")]) == 70
    err = capsys.readouterr().err
    assert "InternalError: RuntimeError: simulated bug" in err and "Traceback (most recent" not in err

    assert cli.main(["--debug", "run", str(tmp_path / "p.falasz")]) == 70
    assert "Traceback (most recent call last)" in capsys.readouterr().err


def test_keyboard_interrupt_exit_130(tmp_path, monkeypatch, capsys):
    write(tmp_path, "p.falasz", "SAY 1\n")

    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "run_file", interrupt)
    assert cli.main(["run", str(tmp_path / "p.falasz")]) == 130
    assert "interrupted" in capsys.readouterr().err


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX pipe semantics")
def test_closed_stdout_pipe_is_not_an_internal_error(tmp_path):
    write(tmp_path, "p.falasz", 'FOR i IN RANGE(0, 200000)\n    SAY "line"\nEND\n')
    proc = subprocess.Popen([sys.executable, "-m", "falasz", "run", "p.falasz"], cwd=tmp_path,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    proc.stdout.read(10)
    proc.stdout.close()
    err = proc.stderr.read().decode()
    proc.wait(timeout=60)
    assert proc.returncode in (0, 1) and "InternalError" not in err


# ============================================================== examples


EXAMPLE_FILES = sorted(list(EXAMPLES.glob("*.falasz")) + [d / "main.falasz" for d in EXAMPLES.iterdir() if d.is_dir()])


@pytest.mark.parametrize("src", EXAMPLE_FILES, ids=lambda p: p.parent.name if p.name == "main.falasz" else p.stem)
def test_examples_through_cli(src, tmp_path):
    import shutil
    workdir = tmp_path / "ex"
    if src.name == "main.falasz":
        shutil.copytree(src.parent, workdir)
    else:
        workdir.mkdir()
        for f in src.parent.glob(src.stem + ".*"):
            shutil.copy(f, workdir)
    args = ["run"]
    if (workdir / (src.stem + ".sensors.json")).exists():
        args += ["--sensors-mock", src.stem + ".sensors.json"]
    stdin_file = workdir / (src.stem + ".in")
    stdin = stdin_file.read_bytes() if stdin_file.exists() else b""
    code, out, err = falasz_cmd(*args, src.name, cwd=workdir, stdin=stdin)
    assert out == (workdir / (src.stem + ".out")).read_bytes()
    expected_err = workdir / (src.stem + ".err")
    if expected_err.exists():
        assert (code, err) == (1, expected_err.read_text(encoding="utf-8"))
    else:
        assert (code, err) == (0, "")
