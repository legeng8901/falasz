"""Stage 5: the `files` module — reading, writing, errors and path handling."""

import contextlib
import io
import ntpath
import os
import posixpath
import sys

import pytest

from falasz import stdlib
from falasz.errors import FalaszError, FalaszFileError
from falasz.runtime import StaticErrors, run_file
from falasz.stdlib import resolve_path

POSIX_ONLY = pytest.mark.skipif(sys.platform == "win32", reason="POSIX-specific")


def write(root, **files):
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8") if isinstance(text, str) else text)
    return root


def run(root, program, cwd=None):
    write(root, **{"main.falasz": program})
    out = io.StringIO()
    with contextlib.chdir(cwd or root):
        run_file(str(root / "main.falasz") if cwd else "main.falasz", out=out)
    return out.getvalue()


def fail(root, program):
    write(root, **{"main.falasz": program})
    with contextlib.chdir(root), pytest.raises((FalaszError, StaticErrors)) as exc:
        run_file("main.falasz", out=io.StringIO())
    return exc.value.errors[0] if isinstance(exc.value, StaticErrors) else exc.value


def file_error(root, program, fragment):
    err = fail(root, program)
    assert err.category == "FileError", err.format()
    assert fragment in err.message, err.message
    return err


# ===================================================== reading and writing


def test_write_then_read_round_trip_unicode(tmp_path):
    program = 'IMPORT files\nfiles.write_text("out.txt", "zażółć\\ngęślą 🙂")\nSAY files.read_text("out.txt")\n'
    assert run(tmp_path, program) == "zażółć\ngęślą 🙂\n"
    assert (tmp_path / "out.txt").read_bytes() == "zażółć\ngęślą 🙂".encode("utf-8")


def test_write_returns_null_and_overwrites(tmp_path):
    program = ('IMPORT files\nSAY files.write_text("o.txt", "first, longer")\n'
               'files.write_text("o.txt", "2nd")\nSAY files.read_text("o.txt")\n')
    assert run(tmp_path, program) == "NULL\n2nd\n"


def test_empty_file(tmp_path):
    program = 'IMPORT files\nfiles.write_text("e.txt", "")\nSAY LEN(files.read_text("e.txt"))\n'
    assert run(tmp_path, program) == "0\n"


def test_no_newline_translation_in_either_direction(tmp_path):
    write(tmp_path, **{"crlf.txt": b"a\r\nb\rc\n"})
    program = ('IMPORT files\nLET t = files.read_text("crlf.txt")\nSAY LEN(t)\n'
               'files.write_text("copy.txt", t + "\\n")\n')
    assert run(tmp_path, program) == "7\n"
    assert (tmp_path / "copy.txt").read_bytes() == b"a\r\nb\rc\n\n"


def test_bom_is_kept_as_a_character(tmp_path):
    write(tmp_path, **{"bom.txt": b"\xef\xbb\xbfx"})
    assert run(tmp_path, 'IMPORT files\nSAY LEN(files.read_text("bom.txt"))\n') == "2\n"


def test_subdirectories_and_dotdot(tmp_path):
    write(tmp_path / "app", **{"data/in.txt": "inner"})
    write(tmp_path, **{"outside.txt": "outer"})
    program = ('IMPORT files\nSAY files.read_text("data/in.txt")\n'
               'SAY files.read_text("../outside.txt")\n')
    # `files` is not a sandbox (spec 9.3): ".." works like in any program.
    assert run(tmp_path / "app", program) == "inner\nouter\n"


def test_absolute_paths(tmp_path):
    target = tmp_path / "abs.txt"
    quoted = '"' + target.as_posix() + '"'  # forward slashes: valid on Windows too, no escapes
    program = f"IMPORT files\nfiles.write_text({quoted}, \"A\")\nSAY files.read_text({quoted})\n"
    assert run(tmp_path / "proj", program) == "A\n"
    assert target.read_text() == "A"


# ============================================ relative path = script directory


def test_relative_paths_use_script_directory_not_cwd(tmp_path):
    write(tmp_path / "proj", **{"data.txt": "right"})
    write(tmp_path / "cwd", **{"data.txt": "wrong"})
    program = 'IMPORT files\nSAY files.read_text("data.txt")\nfiles.write_text("made.txt", "x")\n'
    assert run(tmp_path / "proj", program, cwd=tmp_path / "cwd") == "right\n"
    assert (tmp_path / "proj" / "made.txt").exists()
    assert not (tmp_path / "cwd" / "made.txt").exists()


def test_relative_paths_from_module_function_use_main_script_directory(tmp_path):
    write(tmp_path, **{
        "data.txt": "main dir",
        "reader.falasz": "EXPORT load\nIMPORT files\nFUNC load(p)\n    RETURN files.read_text(p)\nEND\n",
    })
    assert run(tmp_path, 'IMPORT LOCAL reader\nSAY reader.load("data.txt")\n', cwd=tmp_path.parent) == "main dir\n"


def test_cwd_change_after_start_does_not_matter(tmp_path, monkeypatch):
    write(tmp_path / "proj", **{"data.txt": "stable"})
    write(tmp_path / "proj", **{"main.falasz": 'IMPORT files\nLET a = INPUT()\nSAY files.read_text("data.txt")\n'})

    class ChdirOnRead(io.BytesIO):
        def readline(self, *args):
            os.chdir(tmp_path)  # cwd changes while the program runs
            return super().readline(*args)

    out = io.StringIO()
    with contextlib.chdir(tmp_path / "proj"):
        run_file("main.falasz", out=out, inp=ChdirOnRead(b"go\n"))
    assert out.getvalue() == "stable\n"


# ================================================================= errors


def test_missing_file(tmp_path):
    err = file_error(tmp_path, 'IMPORT files\nSAY files.read_text("nope.txt")\n', 'cannot read "nope.txt": no such file')
    assert (err.path, tuple(err.pos)) == ("main.falasz", (2, 20))


def test_write_into_missing_directory_does_not_create_it(tmp_path):
    file_error(tmp_path, 'IMPORT files\nfiles.write_text("no/dir/x.txt", "x")\n', 'cannot write "no/dir/x.txt": no such file')
    assert not (tmp_path / "no").exists()


def test_directory_as_file(tmp_path):
    (tmp_path / "d").mkdir()
    file_error(tmp_path, 'IMPORT files\nSAY files.read_text("d")\n', "is a directory")
    err = fail(tmp_path, 'IMPORT files\nfiles.write_text("d", "x")\n')
    assert err.category == "FileError"


def test_path_through_a_file(tmp_path):
    write(tmp_path, **{"plain.txt": "x"})
    err = fail(tmp_path, 'IMPORT files\nSAY files.read_text("plain.txt/inner")\n')
    assert err.category == "FileError"


@pytest.mark.parametrize("path, fragment", [
    ('""', "must not be empty"),
    ('"a\\nb"', "no such file"),
])
def test_odd_paths(tmp_path, path, fragment):
    file_error(tmp_path, f"IMPORT files\nSAY files.read_text({path})\n", fragment)


def test_nul_character_in_path(tmp_path):
    # A NUL can only come from data (no escape for it), e.g. read from a file.
    write(tmp_path, **{"name.txt": b"a\x00b"})
    file_error(tmp_path, 'IMPORT files\nSAY files.read_text(files.read_text("name.txt"))\n', "NUL character")
    file_error(tmp_path, 'IMPORT files\nfiles.write_text(files.read_text("name.txt"), "x")\n', "NUL character")


def test_invalid_utf8_reports_byte_offset(tmp_path):
    write(tmp_path, **{"bin.dat": b"ok\xff\xfe"})
    file_error(tmp_path, 'IMPORT files\nSAY files.read_text("bin.dat")\n', "not valid UTF-8 (byte offset 2)")


def test_read_size_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(stdlib, "MAX_READ_BYTES", 10)
    write(tmp_path, **{"ten.txt": "0123456789", "eleven.txt": "0123456789A"})
    assert run(tmp_path, 'IMPORT files\nSAY files.read_text("ten.txt")\n') == "0123456789\n"
    file_error(tmp_path, 'IMPORT files\nSAY files.read_text("eleven.txt")\n', "larger than 10 bytes")


@POSIX_ONLY
@pytest.mark.skipif(not os.path.exists("/dev/zero"), reason="needs /dev/zero")
def test_endless_device_is_bounded(tmp_path, monkeypatch):
    monkeypatch.setattr(stdlib, "MAX_READ_BYTES", 1024)
    file_error(tmp_path, 'IMPORT files\nSAY files.read_text("/dev/zero")\n', "larger than 1024 bytes")


@POSIX_ONLY
@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root ignores permissions")
def test_permission_denied(tmp_path):
    write(tmp_path, **{"secret.txt": "x"})
    os.chmod(tmp_path / "secret.txt", 0)
    locked = tmp_path / "locked"
    locked.mkdir()
    os.chmod(locked, 0o500)
    try:
        file_error(tmp_path, 'IMPORT files\nSAY files.read_text("secret.txt")\n', "permission denied")
        file_error(tmp_path, 'IMPORT files\nfiles.write_text("locked/new.txt", "x")\n', "permission denied")
    finally:
        os.chmod(tmp_path / "secret.txt", 0o644)
        os.chmod(locked, 0o700)


@pytest.mark.parametrize("call, fragment", [
    ("files.read_text(1)", "path must be STRING, not INTEGER"),
    ("files.read_text(NULL)", "path must be STRING, not NULL"),
    ('files.write_text(["a"], "x")', "path must be STRING, not LIST"),
    ('files.write_text("a.txt", 5)', "content must be STRING, not INTEGER"),
])
def test_argument_types(tmp_path, call, fragment):
    err = fail(tmp_path, f"IMPORT files\nSAY {call}\n")
    assert err.category == "TypeError" and fragment in err.message


@pytest.mark.parametrize("call, fragment", [
    ("files.read_text()", "files.read_text expects 1 argument(s), got 0"),
    ('files.write_text("a")', "files.write_text expects 2 argument(s), got 1"),
])
def test_arity(tmp_path, call, fragment):
    err = fail(tmp_path, f"IMPORT files\nSAY {call}\n")
    assert err.category == "ArityError" and fragment in err.message


def test_file_error_inside_function_has_traceback_and_user_path(tmp_path):
    err = fail(tmp_path, 'IMPORT files\nFUNC load(p)\n    RETURN files.read_text(p)\nEND\nSAY load("../missing.txt")\n')
    assert err.category == "FileError"
    assert '"../missing.txt"' in err.message  # the path as the user wrote it
    assert str(tmp_path) not in err.message
    assert [e.name for e in err.trace] == ["<main>", "load"]


def test_failed_write_leaves_existing_file_untouched_when_open_fails(tmp_path):
    (tmp_path / "d").mkdir()
    fail(tmp_path, 'IMPORT files\nfiles.write_text("d/", "x")\n')
    assert (tmp_path / "d").is_dir()


# ======================================================== path resolution


@pytest.mark.parametrize("path, expected", [
    ("data.txt", "/base/dir/data.txt"),
    ("./a/../b.txt", "/base/dir/b.txt"),
    ("../up.txt", "/base/up.txt"),
    ("/abs/x.txt", "/abs/x.txt"),
    ("a//b", "/base/dir/a/b"),
])
def test_resolve_posix(path, expected):
    assert resolve_path(path, "/base/dir", posixpath) == expected


@pytest.mark.parametrize("path, expected", [
    ("data.txt", "D:\\proj\\data.txt"),
    ("sub/x.txt", "D:\\proj\\sub\\x.txt"),
    ("C:\\abs\\x.txt", "C:\\abs\\x.txt"),
    ("C:/abs/x.txt", "C:\\abs\\x.txt"),
    ("\\root.txt", "D:\\root.txt"),  # root of the *script's* drive, not the current one
    ("/root.txt", "D:\\root.txt"),
    ("\\\\server\\share\\f.txt", "\\\\server\\share\\f.txt"),
])
def test_resolve_windows(path, expected):
    assert resolve_path(path, "D:\\proj", ntpath) == expected


@pytest.mark.parametrize("path", ["C:data.txt", "c:..\\x"])
def test_windows_drive_relative_paths_are_rejected(path):
    with pytest.raises(FalaszFileError, match="drive-relative"):
        resolve_path(path, "D:\\proj", ntpath)


@pytest.mark.parametrize("pathmod", [posixpath, ntpath])
def test_resolve_rejects_empty_and_nul(pathmod):
    with pytest.raises(FalaszFileError, match="empty"):
        resolve_path("", "/base", pathmod)
    with pytest.raises(FalaszFileError, match="NUL"):
        resolve_path("a\0b", "/base", pathmod)


def test_colon_is_an_ordinary_character_on_posix():
    assert resolve_path("C:data.txt", "/base", posixpath) == "/base/C:data.txt"
