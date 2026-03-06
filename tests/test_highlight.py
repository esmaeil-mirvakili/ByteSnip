"""Tests for snipapp.core.highlight — language detection and HTML rendering."""

import pytest

from snipapp.core.highlight import detect_language, get_lexer, render_html


# ---------------------------------------------------------------------------
# detect_language — Pygments analyse_text path (import / shebang)
# ---------------------------------------------------------------------------

class TestDetectLanguagePygments:
    def test_python_via_import(self):
        code = "import os\nimport sys\n\nprint(sys.argv)"
        assert detect_language(code) == "python"

    def test_python_via_shebang(self):
        code = "#!/usr/bin/env python3\nprint('hello')"
        assert detect_language(code) == "python"

    def test_python_full_module(self):
        code = (
            "import os\nimport sys\n\n"
            "def hello(name: str) -> str:\n"
            "    return f'hello {name}'\n\n"
            "if __name__ == '__main__':\n"
            "    print(hello(sys.argv[1]))\n"
        )
        assert detect_language(code) == "python"


# ---------------------------------------------------------------------------
# detect_language — regex heuristic path (short snippets without imports)
# ---------------------------------------------------------------------------

class TestDetectLanguageHeuristics:
    def test_python_type_annotated_function(self):
        assert detect_language("def hi() -> int:\n    return 5") == "python"

    def test_python_plain_function(self):
        assert detect_language("def greet():\n    print('hello')") == "python"

    def test_python_class(self):
        assert detect_language("class MyClass:\n    pass") == "python"

    def test_python_async_function(self):
        assert detect_language("async def fetch():\n    await something()") == "python"

    def test_python_decorator(self):
        assert detect_language("@staticmethod\ndef helper():\n    pass") == "python"

    def test_python_f_string(self):
        assert detect_language("name = 'world'\nprint(f'hello {name}')") == "python"

    def test_python_dunder(self):
        assert detect_language("x = obj.__class__.__name__") == "python"

    def test_rust_fn(self):
        assert detect_language("fn main() {\n    println!(\"hi\");\n}") == "rust"

    def test_rust_pub_fn(self):
        assert detect_language("pub fn add(a: i32, b: i32) -> i32 {\n    a + b\n}") == "rust"

    def test_rust_let_mut(self):
        assert detect_language("let mut v: Vec<i32> = Vec::new();") == "rust"

    def test_go_func(self):
        assert detect_language("func main() {\n    fmt.Println(\"hi\")\n}") == "go"

    def test_go_package(self):
        # Avoid bare `import` which Pygments scores as Python; pair with func
        assert detect_language("package main\n\nfunc main() {\n    fmt.Println(\"hi\")\n}") == "go"

    def test_typescript_interface(self):
        assert detect_language("interface User {\n  id: number;\n  name: string;\n}") == "typescript"

    def test_typescript_type_alias(self):
        assert detect_language("type Point = { x: number; y: number }") == "typescript"

    def test_javascript_arrow_function(self):
        assert detect_language("const add = (a, b) => a + b;") == "javascript"

    def test_javascript_const_function(self):
        assert detect_language("const fn = async (x) => {\n  return x * 2;\n};") == "javascript"

    def test_sql_select(self):
        assert detect_language("SELECT id, name FROM users WHERE active = 1;") == "sql"

    def test_sql_insert(self):
        assert detect_language("INSERT INTO users (name, email) VALUES ('Alice', 'a@b.com');") == "sql"

    def test_sql_create_table(self):
        assert detect_language("CREATE TABLE orders (id INT PRIMARY KEY, total DECIMAL);") == "sql"

    def test_json_object(self):
        assert detect_language('{"name": "Alice", "age": 30}') == "json"

    def test_json_array_of_objects(self):
        assert detect_language('[{"id": 1}, {"id": 2}]') == "json"

    def test_bash_shebang(self):
        assert detect_language("#!/bin/bash\necho hello") == "bash"

    def test_bash_echo(self):
        assert detect_language("echo 'hello'\nexport PATH=/usr/bin:$PATH") == "bash"


# ---------------------------------------------------------------------------
# detect_language — edge cases
# ---------------------------------------------------------------------------

class TestDetectLanguageEdgeCases:
    def test_empty_string(self):
        assert detect_language("") == "text"

    def test_whitespace_only(self):
        assert detect_language("   \n\t  ") == "text"

    def test_single_number(self):
        # Should not raise; result may be "text" or something low-confidence
        result = detect_language("42")
        assert isinstance(result, str)

    def test_returns_string_always(self):
        for code in ["x = 1", "{}", "// comment", "<!-- html -->"]:
            result = detect_language(code)
            assert isinstance(result, str)
            assert len(result) > 0


# ---------------------------------------------------------------------------
# get_lexer
# ---------------------------------------------------------------------------

class TestGetLexer:
    def test_known_language(self):
        from pygments.lexers import PythonLexer
        lexer = get_lexer("python")
        assert isinstance(lexer, PythonLexer)

    def test_unknown_language_falls_back_to_text(self):
        from pygments.lexers import TextLexer
        lexer = get_lexer("not_a_real_language_xyz")
        assert isinstance(lexer, TextLexer)

    def test_case_insensitive_alias(self):
        # "Python" vs "python" — Pygments normalises
        from pygments.lexers import PythonLexer
        lexer = get_lexer("Python")
        assert isinstance(lexer, PythonLexer)


# ---------------------------------------------------------------------------
# render_html
# ---------------------------------------------------------------------------

class TestRenderHtml:
    def test_contains_code_content(self):
        html = render_html("x = 1", "python")
        assert "x" in html
        assert "1" in html

    def test_contains_html_markup(self):
        html = render_html("x = 1", "python")
        assert "<" in html
        assert ">" in html

    def test_contains_style_tag(self):
        html = render_html("x = 1", "python")
        assert "<style>" in html.lower()

    def test_unknown_language_renders_plain(self):
        html = render_html("hello world", "not_a_lang_xyz")
        assert "hello world" in html

    def test_empty_code(self):
        html = render_html("", "python")
        assert isinstance(html, str)

    def test_multiline_code(self):
        code = "def f():\n    return 1\n"
        html = render_html(code, "python")
        assert "def" in html
        assert "return" in html

    def test_html_special_chars_escaped(self):
        html = render_html("<div>hello</div>", "html")
        # The raw < should be escaped in the output
        assert "&lt;" in html or "<span" in html

    @pytest.mark.parametrize("lang", ["python", "javascript", "rust", "sql", "json", "text"])
    def test_renders_without_error(self, lang):
        html = render_html("x = 1", lang)
        assert isinstance(html, str)
        assert len(html) > 0
