"""CodePreview widget: renders syntax-highlighted HTML in a QTextBrowser."""

from __future__ import annotations

from PySide6.QtWidgets import QTextBrowser, QWidget

from snipapp.core.highlight import render_html


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class CodePreview(QTextBrowser):
    """A read-only pane that shows syntax-highlighted code snippets."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setOpenLinks(False)
        self.setMinimumWidth(300)
        self._apply_base_style()

    def show_snippet(
        self,
        code: str,
        language: str = "text",
        description: str = "",
        title: str = "",
        tags: list[str] | None = None,
    ) -> None:
        """Render *code* with syntax highlighting, preceded by a rich metadata header.

        When *title* or *tags* are provided the header expands to show them.
        This richer form is used in the picker preview; the save-window preview
        leaves those fields empty and just shows the language badge + description.
        """
        header_html = _build_header_html(title, language, description, tags or [])
        code_html = render_html(code, language)
        self.setHtml(header_html + code_html)

    def clear_preview(self) -> None:
        self.setHtml("")

    def _apply_base_style(self) -> None:
        self.setStyleSheet(
            "QTextBrowser { background: #272822; border: none; }"
        )


def _build_header_html(
    title: str, language: str, description: str, tags: list[str]
) -> str:
    """Return an HTML block for the metadata header, or '' if nothing to show."""
    show_lang = bool(language and language != "text")
    if not any([title, description, show_lang, tags]):
        return ""

    parts: list[str] = []

    # ── Title row + language badge ────────────────────────────────────────
    title_cell = (
        f'<span style="font-size:14px; font-weight:bold; color:#e2e2e2;">'
        f"{_esc(title)}</span>"
        if title
        else ""
    )
    lang_cell = (
        f'<span style="background:#1e3a4a; color:#9cdcfe; border-radius:3px;'
        f" padding:2px 8px; font-family:monospace; font-size:10px;"
        f'">{_esc(language)}</span>'
        if show_lang
        else ""
    )
    if title_cell or lang_cell:
        parts.append(
            '<table width="100%" cellpadding="0" cellspacing="0"'
            ' style="margin-bottom:6px;">'
            "<tr>"
            f'<td style="vertical-align:bottom; padding:0;">{title_cell}</td>'
            f'<td style="text-align:right; vertical-align:bottom; padding:0;'
            f' white-space:nowrap;">{lang_cell}</td>'
            "</tr></table>"
        )
    elif show_lang and not title_cell:
        # No title — still show lang badge left-aligned
        parts.append(f'<div style="margin-bottom:6px;">{lang_cell}</div>')

    # ── Description ──────────────────────────────────────────────────────
    if description:
        parts.append(
            f'<div style="font-size:12px; color:#888888; margin-bottom:6px;">'
            f"{_esc(description)}</div>"
        )

    # ── Tags ─────────────────────────────────────────────────────────────
    if tags:
        chips = "&nbsp;".join(
            f'<span style="background:#1e3050; color:#4ec9b0; border-radius:10px;'
            f" padding:2px 9px; font-size:11px;"
            f'">{_esc(t)}</span>'
            for t in tags
        )
        parts.append(f'<div style="margin-top:2px;">{chips}</div>')

    return (
        '<div style="font-family:sans-serif; padding:14px 16px 12px 16px;'
        " background:#1a1a1a; border-bottom:1px solid #3a3a3a;"
        '">'
        + "".join(parts)
        + "</div>"
    )
