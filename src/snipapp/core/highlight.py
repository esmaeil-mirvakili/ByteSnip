"""Syntax highlighting via Pygments: lexer detection and HTML rendering."""

from __future__ import annotations

import logging
import re

from pygments import highlight
from pygments.formatter import Formatter
from pygments.formatters import HtmlFormatter
from pygments.lexer import Lexer
from pygments.lexers import TextLexer, get_lexer_by_name, guess_lexer
from pygments.util import ClassNotFound

logger = logging.getLogger(__name__)

_HTML_FORMATTER = HtmlFormatter(
    style="monokai",
    noclasses=True,
    prestyles="margin:0; padding:8px; font-family: monospace; font-size: 13px;",
)

# Common languages probed via Pygments analyse_text, in priority order.
_CANDIDATE_LANGUAGES = [
    "python", "typescript", "javascript", "rust", "go", "kotlin",
    "java", "swift", "csharp", "cpp", "c", "ruby", "php",
    "bash", "sql", "html", "css", "json", "yaml", "toml", "markdown",
]

# Regex-based heuristics used when Pygments analyse_text scores everything 0.
# Each entry: (language_alias, score, pattern, re_flags)
# Patterns are tried on the full code string; first match applies the score.
_HEURISTICS: list[tuple[str, float, str, int]] = [
    # Python — type-annotated function is unambiguous
    ("python", 0.95, r"def\s+\w+\s*\([^)]*\)\s*->", 0),
    # Python — plain function/class definition ending with colon
    ("python", 0.80, r"^\s*(def|class|async\s+def)\s+\w+", re.MULTILINE),
    # Python — import statements
    ("python", 0.90, r"^\s*(import\s+\w|from\s+\w[\w.]*\s+import)", re.MULTILINE),
    # Python — decorators
    ("python", 0.80, r"^\s*@\w+(\.\w+)*\s*$", re.MULTILINE),
    # Python — f-strings, elif, lambda, yield, pass, None/True/False
    ("python", 0.75, r'f["\'][^"\']*\{|\belif\b|\blambda\b|\byield\b|\b__\w+__\b', 0),
    # Rust — fn keyword with return arrow or let mut
    ("rust", 0.90, r"\bfn\s+\w+\s*(<[^>]*>)?\s*\(", 0),
    ("rust", 0.85, r"\blet\s+mut\b|\bimpl\b|\bpub\s+(fn|struct|enum|trait)\b", 0),
    # Go — func keyword or package declaration
    ("go", 0.90, r"^(func|package)\s+\w+", re.MULTILINE),
    # TypeScript — interface, type alias, or typed arrow functions
    ("typescript", 0.90, r"\binterface\s+\w+\s*\{|\btype\s+\w+\s*=|\w+:\s*\w+\[\]", 0),
    # JavaScript — const/let/var with arrow functions
    ("javascript", 0.75, r"\b(const|let|var)\s+\w+\s*=\s*(async\s+)?\(", 0),
    # Java/Kotlin — class with public/private modifiers
    ("java", 0.80, r"\b(public|private|protected)\s+(static\s+)?\w+\s+\w+\s*[\(\{]", 0),
    # Shell — shebang or common shell constructs
    ("bash", 0.90, r"^#!\s*/bin/(ba)?sh|^\$\s+\w", re.MULTILINE),
    ("bash", 0.75, r"\b(echo|export|source|chmod|grep|awk|sed)\b", 0),
    # SQL — SELECT/INSERT/UPDATE/CREATE
    ("sql", 0.90, r"(?i)^\s*(SELECT|INSERT\s+INTO|UPDATE\s+\w|CREATE\s+(TABLE|INDEX))", re.MULTILINE),
    # JSON — object starting with double-quoted key, or array-of-objects
    ("json", 0.90, r'^\s*\{(\s|\n)*"[^"]+"\s*:', re.MULTILINE),
    ("json", 0.85, r'^\s*\[(\s|\n)*\{(\s|\n)*"[^"]+"\s*:', re.MULTILINE),
]


def detect_language(code: str) -> str:
    """Guess the language of *code*; returns a Pygments alias or 'text'.

    Strategy:
    1. Probe common lexers via Pygments ``analyse_text`` (fast, reliable for
       files with import/shebang lines).
    2. If all score 0, apply regex heuristics (handles short snippets that
       lack import statements — e.g. ``def hi() -> int: ...``).
    3. Last resort: ``guess_lexer`` (avoids obscure false positives in steps
       1-2 but is still available for unusual languages).
    """
    if not code.strip():
        return "text"

    # --- Step 1: Pygments analyse_text ---
    best_lang = "text"
    best_score = 0.0
    for lang in _CANDIDATE_LANGUAGES:
        try:
            lexer_cls = type(get_lexer_by_name(lang))
            score = float(lexer_cls.analyse_text(code) or 0.0)
            if score > best_score:
                best_score = score
                best_lang = lang
        except (ClassNotFound, Exception):
            continue

    if best_score > 0.0:
        logger.debug("Detected language: %s (pygments, score=%.2f)", best_lang, best_score)
        return best_lang

    # --- Step 2: regex heuristics ---
    for lang, score, pattern, flags in _HEURISTICS:
        if re.search(pattern, code, flags):
            logger.debug("Detected language: %s (heuristic, score=%.2f)", lang, score)
            return lang

    # --- Step 3: guess_lexer fallback ---
    try:
        lexer = guess_lexer(code)
        if not isinstance(lexer, TextLexer):
            name = lexer.aliases[0] if lexer.aliases else "text"
            logger.debug("Detected language: %s (guess_lexer)", name)
            return name
    except ClassNotFound:
        pass

    return "text"


def get_lexer(language: str) -> Lexer:
    """Return a Pygments lexer for *language*, falling back to TextLexer."""
    try:
        return get_lexer_by_name(language, stripall=True)
    except ClassNotFound:
        return TextLexer()


def render_html(code: str, language: str = "text") -> str:
    """Return a self-contained HTML string with syntax-highlighted *code*."""
    lexer = get_lexer(language)
    highlighted = highlight(code, lexer, _HTML_FORMATTER)
    css = _HTML_FORMATTER.get_style_defs()
    return f"<style>{css}</style>{highlighted}"


def get_formatter() -> Formatter:
    return _HTML_FORMATTER
