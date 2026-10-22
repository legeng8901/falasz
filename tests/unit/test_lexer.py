import pytest

from falasz.errors import FalaszLimitError, FalaszSyntaxError, Pos
from falasz.lexer import MAX_SOURCE_BYTES, decode_source, tokenize
from falasz.tokens import T


def types(src):
    return [t.type for t in tokenize(src)]


def texts(src):
    return [t.text for t in tokenize(src) if t.type not in (T.NEWLINE, T.EOF)]


def syntax_error(src):
    with pytest.raises(FalaszSyntaxError) as exc:
        tokenize(src, "t.falasz")
    return exc.value


# ------------------------------------------------------------------ structure


def test_empty_source():
    assert types("") == [T.EOF]
    assert types("\n\n# only a comment\n") == [T.EOF]


def test_statement_gets_trailing_newline_even_without_one_in_file():
    assert types("SAY 1") == [T.SAY, T.INTEGER, T.NEWLINE, T.EOF]


def test_blank_lines_collapse():
    assert types("SAY 1\n\n\n  \nSAY 2\n") == [
        T.SAY, T.INTEGER, T.NEWLINE, T.SAY, T.INTEGER, T.NEWLINE, T.EOF,
    ]


@pytest.mark.parametrize("nl", ["\n", "\r\n", "\r"])
def test_line_endings_are_equivalent(nl):
    toks = tokenize(f"LET a = 1{nl}SAY a{nl}")
    assert [t.type for t in toks] == [
        T.LET, T.IDENT, T.ASSIGN, T.INTEGER, T.NEWLINE, T.SAY, T.IDENT, T.NEWLINE, T.EOF,
    ]
    assert toks[5].pos == Pos(2, 1)
    assert toks[-1].pos == Pos(3, 1)


def test_newlines_ignored_inside_brackets():
    src = "SAY f(1,\n  2) + [3,\n4] + {\n\"a\": 1\n}\nSAY 2\n"
    assert types(src).count(T.NEWLINE) == 2


def test_comments():
    assert texts('SAY 1 # comment "x"\n# full line\nSAY "# not a comment"') == [
        "SAY", "1", "SAY", "# not a comment",
    ]


def test_positions_count_code_points_and_tabs_as_one_column():
    toks = tokenize('SAY "żółw" +\tx')
    assert toks[2].pos == Pos(1, 12)
    assert toks[3].pos == Pos(1, 14)


# ------------------------------------------------------------------- keywords


def test_keywords_are_uppercase_only():
    assert types("LET let Let IF if LOCAL local AS as EXPORT")[:-2] == [
        T.LET, T.IDENT, T.IDENT, T.IF, T.IDENT, T.LOCAL, T.IDENT, T.AS, T.IDENT, T.EXPORT,
    ]


def test_builtins_are_identifiers_not_keywords():
    assert {t.type for t in tokenize("RANGE STR INT FLOAT LEN INPUT")} == {T.IDENT, T.NEWLINE, T.EOF}


def test_all_keywords_recognised():
    words = ("LET SAY IF ELSE WHILE FOR IN FUNC RETURN END BREAK CONTINUE "
             "IMPORT LOCAL AS EXPORT TRUE FALSE NULL AND OR NOT").split()
    assert [t.type.value for t in tokenize(" ".join(words))[:-2]] == words


def test_identifiers():
    assert texts("_a a_1 B2 __") == ["_a", "a_1", "B2", "__"]


def test_non_ascii_identifier_rejected():
    err = syntax_error("LET zażółć = 1")
    assert err.pos == Pos(1, 7)  # the 'ż'
    assert "ASCII" in err.message


# ------------------------------------------------------------------- literals


def test_numbers():
    toks = tokenize("0 42 3.5 0.25 10.0")
    assert [(t.type, t.text) for t in toks[:-2]] == [
        (T.INTEGER, "0"), (T.INTEGER, "42"), (T.FLOAT, "3.5"), (T.FLOAT, "0.25"), (T.FLOAT, "10.0"),
    ]


@pytest.mark.parametrize("src, col", [
    ("SAY 1.", 5), ("SAY 1.x", 5), ("SAY 007", 5), ("SAY 00.5", 5), ("SAY 12abc", 5), ("SAY 1.5.2", 5),
])
def test_bad_numbers(src, col):
    assert syntax_error(src).pos == Pos(1, col)


def test_leading_dot_float_is_not_a_number():
    assert types(".5")[:2] == [T.DOT, T.INTEGER]


def test_minus_is_an_operator():
    assert types("-1")[:2] == [T.MINUS, T.INTEGER]


def test_strings_and_escapes():
    toks = tokenize(r'"a\"b\\c\nd\te" ""')
    assert toks[0].text == 'a"b\\c\nd\te'
    assert toks[1].text == ""


def test_string_with_unicode():
    assert texts('"zażółć 🙂"') == ["zażółć 🙂"]


@pytest.mark.parametrize("src", ['SAY "abc', 'SAY "abc\nSAY 1'])
def test_unterminated_string_points_at_opening_quote(src):
    err = syntax_error(src)
    assert err.pos == Pos(1, 5)
    assert "unterminated" in err.message


def test_invalid_escape():
    err = syntax_error(r'SAY "a\qb"')
    assert err.pos == Pos(1, 7)
    assert "\\q" in err.message


# ------------------------------------------------------------------ operators


def test_operators_longest_match():
    assert types("<= < >= > == = != + - * / % ( ) [ ] { } , . :")[:-2] == [
        T.LE, T.LT, T.GE, T.GT, T.EQ, T.ASSIGN, T.NE, T.PLUS, T.MINUS, T.STAR, T.SLASH,
        T.PERCENT, T.LPAREN, T.RPAREN, T.LBRACKET, T.RBRACKET, T.LBRACE, T.RBRACE,
        T.COMMA, T.DOT, T.COLON,
    ]


@pytest.mark.parametrize("ch", ["!", "&", "|", ";", "$", "@", "'", "^"])
def test_unknown_characters(ch):
    err = syntax_error(f"SAY 1 {ch} 2")
    assert err.pos == Pos(1, 7)


# ------------------------------------------------------------------- decoding


def test_decode_strips_bom():
    assert decode_source(b"\xef\xbb\xbfSAY 1", "t") == "SAY 1"


def test_decode_invalid_utf8_reports_position():
    data = 'SAY 1\nSAY "ż'.encode("utf-8") + b"\xff"
    with pytest.raises(FalaszSyntaxError) as exc:
        decode_source(data, "t.falasz")
    assert exc.value.pos == Pos(2, 7)


def test_decode_size_limit():
    with pytest.raises(FalaszLimitError):
        decode_source(b" " * (MAX_SOURCE_BYTES + 1), "t")
    assert decode_source(b" " * MAX_SOURCE_BYTES, "t")


def test_error_format_contains_path_line_column():
    err = syntax_error("SAY 1 $")
    assert err.format() == "t.falasz:1:7: SyntaxError: unexpected character '$'"
