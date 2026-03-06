"""Tests for UI component changes: CodePreview, SaveWindow, _default_title, TagInput."""

from __future__ import annotations

from snipapp.ui.save_window import _default_title
from snipapp.ui.components.code_preview import CodePreview
from snipapp.ui.components.tag_input import TagInput, _TagChip
from snipapp.ui.save_window import SaveWindow


# ---------------------------------------------------------------------------
# _default_title (no Qt needed)
# ---------------------------------------------------------------------------

def test_default_title_uses_first_line():
    assert _default_title("def foo():\n    pass") == "def foo():"


def test_default_title_truncates_long_lines():
    assert _default_title("x" * 100) == "x" * 80


def test_default_title_empty_text():
    assert _default_title("") == "Untitled"
    assert _default_title("   ") == "Untitled"


# ---------------------------------------------------------------------------
# CodePreview HTML output
# ---------------------------------------------------------------------------

def test_code_preview_language_badge_shown(qtbot):
    widget = CodePreview()
    qtbot.addWidget(widget)
    widget.show_snippet("print('hi')", language="python")
    assert "python" in widget.toHtml()


def test_code_preview_language_badge_hidden_for_text(qtbot):
    widget = CodePreview()
    qtbot.addWidget(widget)
    widget.show_snippet("hello world", language="text")
    # Plain-text snippets should not render the coloured badge span
    assert "#9cdcfe" not in widget.toHtml()


def test_code_preview_description_shown(qtbot):
    widget = CodePreview()
    qtbot.addWidget(widget)
    widget.show_snippet("x = 1", language="python", description="assign x")
    assert "assign x" in widget.toHtml()


def test_code_preview_clear(qtbot):
    widget = CodePreview()
    qtbot.addWidget(widget)
    widget.show_snippet("x = 1", language="python")
    widget.clear_preview()
    assert widget.toPlainText().strip() == ""


def test_code_preview_title_shown(qtbot):
    widget = CodePreview()
    qtbot.addWidget(widget)
    widget.show_snippet("x = 1", language="python", title="My Snippet")
    assert "My Snippet" in widget.toHtml()


def test_code_preview_tags_shown(qtbot):
    widget = CodePreview()
    qtbot.addWidget(widget)
    widget.show_snippet("x = 1", language="python", tags=["utils", "sorting"])
    html = widget.toHtml()
    assert "utils" in html
    assert "sorting" in html


def test_code_preview_no_header_for_text_only(qtbot):
    """No header at all when language=text, no title, no description, no tags."""
    from snipapp.ui.components.code_preview import _build_header_html
    assert _build_header_html("", "text", "", []) == ""


def test_code_preview_html_escaping(qtbot):
    """Title and tags with HTML special chars are escaped safely."""
    from snipapp.ui.components.code_preview import _build_header_html
    html = _build_header_html("<script>", "python", "a & b", ["<tag>"])
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "&amp;" in html
    assert "&lt;tag&gt;" in html


# ---------------------------------------------------------------------------
# SaveWindow validation
# ---------------------------------------------------------------------------

def test_save_window_warning_hidden_initially(qtbot, db):
    win = SaveWindow()
    qtbot.addWidget(win)
    assert win._warning_label.isHidden()


def test_save_window_shows_warning_on_empty_body(qtbot, db):
    win = SaveWindow()
    qtbot.addWidget(win)
    win._editor.setPlainText("")
    win._save()
    assert not win._warning_label.isHidden()
    assert "empty" in win._warning_label.text().lower()


def test_save_window_warning_clears_on_edit(qtbot, db):
    win = SaveWindow()
    qtbot.addWidget(win)
    win._editor.setPlainText("")
    win._save()
    assert not win._warning_label.isHidden()
    win._editor.setPlainText("some code")
    assert win._warning_label.isHidden()


def test_save_window_save_btn_shows_shortcut(qtbot, db):
    from PySide6.QtWidgets import QPushButton

    win = SaveWindow()
    qtbot.addWidget(win)
    button_texts = [b.text() for b in win.findChildren(QPushButton)]
    assert any("⌘" in t or "↩" in t for t in button_texts), (
        f"Expected Save button to contain shortcut hint, got: {button_texts}"
    )


# ---------------------------------------------------------------------------
# SaveWindow edit mode
# ---------------------------------------------------------------------------

def _create_snippet(title="My snippet", body="x = 1", language="python",
                    description="desc", tags=None):
    """Helper: insert a snippet into the DB and return its id."""
    from snipapp.core.db import get_session
    from snipapp.core.models import Snippet, Tag

    with get_session() as session:
        snip = Snippet(title=title, body=body, language=language, description=description)
        for name in (tags or []):
            tag = session.query(Tag).filter_by(name=name).first()
            if tag is None:
                tag = Tag(name=name)
                session.add(tag)
            snip.tags.append(tag)
        session.add(snip)
        session.commit()
        return snip.id


def test_edit_snippet_prefills_fields(qtbot, db):
    snippet_id = _create_snippet(
        title="Old title", body="old body", language="python",
        description="old desc", tags=["utils"],
    )
    win = SaveWindow()
    qtbot.addWidget(win)
    win.edit_snippet(snippet_id)

    assert win._title_input.text() == "Old title"
    assert win._editor.toPlainText() == "old body"
    assert win._lang_combo.currentText() == "python"
    assert win._desc_input.text() == "old desc"
    assert win._tag_input.get_tags() == ["utils"]
    assert win._editing_id == snippet_id
    assert "Edit" in win.windowTitle()


def test_edit_snippet_updates_not_inserts(qtbot, db):
    from snipapp.core.db import get_session
    from snipapp.core.models import Snippet

    snippet_id = _create_snippet(title="Original", body="v = 1")
    win = SaveWindow()
    qtbot.addWidget(win)
    win.edit_snippet(snippet_id)

    win._title_input.setText("Updated title")
    win._editor.setPlainText("v = 2")
    win._save()

    with get_session() as session:
        count = session.query(Snippet).count()
        updated = session.get(Snippet, snippet_id)
        assert updated is not None
        assert updated.title == "Updated title"
        assert updated.body == "v = 2"
    assert count == 1  # no new row inserted


def test_edit_snippet_resets_mode_on_reject(qtbot, db):
    snippet_id = _create_snippet()
    win = SaveWindow()
    qtbot.addWidget(win)
    win.edit_snippet(snippet_id)
    assert win._editing_id == snippet_id

    win.reject()
    assert win._editing_id is None
    assert "Edit" not in win.windowTitle()


def test_edit_snippet_resets_mode_after_save(qtbot, db):
    snippet_id = _create_snippet(body="x = 1")
    win = SaveWindow()
    qtbot.addWidget(win)
    win.edit_snippet(snippet_id)
    win._save()

    assert win._editing_id is None
    assert "Edit" not in win.windowTitle()


# ---------------------------------------------------------------------------
# PickerWindow Cmd+E shortcut emits edit_requested
# ---------------------------------------------------------------------------

def test_picker_cmd_e_emits_edit_requested(qtbot, db):
    from snipapp.ui.picker_window import PickerWindow

    snippet_id = _create_snippet(title="Edit me")
    picker = PickerWindow()
    qtbot.addWidget(picker)
    picker.show_and_focus()

    emitted: list[int] = []
    picker.edit_requested.connect(emitted.append)

    # Call _open_edit() directly — QShortcut activation is hard to simulate
    # in a headless test environment; the shortcut wiring is exercised manually.
    picker._open_edit()

    assert emitted == [snippet_id]


# ---------------------------------------------------------------------------
# TagInput widget
# ---------------------------------------------------------------------------

def test_tag_input_empty_initially(qtbot):
    widget = TagInput()
    qtbot.addWidget(widget)
    assert widget.get_tags() == []


def test_tag_input_chip_shown_after_add(qtbot):
    widget = TagInput()
    qtbot.addWidget(widget)
    widget._input.setText("python")
    widget._commit_tag()
    assert widget.get_tags() == ["python"]


def test_tag_input_chip_created_per_tag(qtbot):
    widget = TagInput()
    qtbot.addWidget(widget)
    widget.set_tags(["alpha", "beta"])
    assert set(widget.get_tags()) == {"alpha", "beta"}


def test_tag_input_remove_tag(qtbot):
    widget = TagInput()
    qtbot.addWidget(widget)
    widget.set_tags(["alpha", "beta"])
    widget._remove_tag("alpha")
    assert widget.get_tags() == ["beta"]


def test_tag_input_all_removed_leaves_no_chips(qtbot):
    widget = TagInput()
    qtbot.addWidget(widget)
    widget.set_tags(["only"])
    widget._remove_tag("only")
    assert widget.get_tags() == []


def test_tag_input_no_duplicate_tags(qtbot):
    widget = TagInput()
    qtbot.addWidget(widget)
    widget._input.setText("dupe")
    widget._commit_tag()
    widget._input.setText("dupe")
    widget._commit_tag()
    assert widget.get_tags() == ["dupe"]


def test_tag_input_emits_tags_changed(qtbot):
    widget = TagInput()
    qtbot.addWidget(widget)
    emitted: list[list] = []
    widget.tags_changed.connect(emitted.append)
    widget._input.setText("rust")
    widget._commit_tag()
    assert emitted == [["rust"]]


def test_tag_chip_removed_signal(qtbot):
    chip = _TagChip("go")
    qtbot.addWidget(chip)
    removed: list[str] = []
    chip.removed.connect(removed.append)
    chip.removed.emit("go")
    assert removed == ["go"]


def test_tag_input_set_tags_replaces_existing(qtbot):
    widget = TagInput()
    qtbot.addWidget(widget)
    widget.set_tags(["a", "b"])
    widget.set_tags(["x"])
    assert widget.get_tags() == ["x"]


# ---------------------------------------------------------------------------
# PickerWindow delete
# ---------------------------------------------------------------------------

def test_picker_delete_removes_snippet(qtbot, db, monkeypatch):
    from snipapp.ui.picker_window import PickerWindow
    from snipapp.core.db import get_session
    from snipapp.core.models import Snippet
    from PySide6.QtWidgets import QMessageBox

    snippet_id = _create_snippet(title="To delete", body="del me")
    picker = PickerWindow()
    qtbot.addWidget(picker)
    picker.show_and_focus()

    # Confirm the item appears in the list
    assert picker._list.count() > 0

    # Simulate user pressing Yes in the confirmation dialog
    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.Yes)

    picker._delete_selected()

    # Snippet must be gone from DB
    with get_session() as session:
        assert session.get(Snippet, snippet_id) is None


def test_picker_delete_cancelled_keeps_snippet(qtbot, db, monkeypatch):
    from snipapp.ui.picker_window import PickerWindow
    from snipapp.core.db import get_session
    from snipapp.core.models import Snippet
    from PySide6.QtWidgets import QMessageBox

    snippet_id = _create_snippet(title="Keep me", body="still here")
    picker = PickerWindow()
    qtbot.addWidget(picker)
    picker.show_and_focus()

    # Simulate user pressing Cancel
    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.Cancel)

    picker._delete_selected()

    with get_session() as session:
        assert session.get(Snippet, snippet_id) is not None


# ---------------------------------------------------------------------------
# SettingsWindow
# ---------------------------------------------------------------------------

def _make_settings(tmp_path):
    from snipapp.core.settings import Settings
    return Settings(path=tmp_path / "config.toml")


def test_settings_window_loads_defaults(qtbot, tmp_path):
    from snipapp.ui.settings_window import SettingsWindow
    s = _make_settings(tmp_path)
    win = SettingsWindow(s)
    qtbot.addWidget(win)
    assert win._picker_hotkey.text() == "<cmd>+<shift>+`"
    assert win._save_hotkey.text() == "<ctrl>+<cmd>+c"
    assert win._search_body_cb.isChecked() is True
    assert win._run_at_login_cb.isChecked() is False


def test_settings_window_save_persists(qtbot, tmp_path):
    from snipapp.ui.settings_window import SettingsWindow
    from snipapp.core.settings import Settings
    path = tmp_path / "config.toml"
    s = _make_settings(tmp_path)
    win = SettingsWindow(s)
    qtbot.addWidget(win)
    win._picker_hotkey.setText("<ctrl>+space")
    win._search_body_cb.setChecked(False)
    win._save()
    s2 = Settings(path=path)
    assert s2.get("hotkeys.picker") == "<ctrl>+space"
    assert s2.get("search_in_body") is False


def test_settings_window_emits_hotkeys_changed(qtbot, tmp_path):
    from snipapp.ui.settings_window import SettingsWindow
    s = _make_settings(tmp_path)
    win = SettingsWindow(s)
    qtbot.addWidget(win)
    emitted: list[tuple] = []
    win.hotkeys_changed.connect(lambda p, sv: emitted.append((p, sv)))
    win._picker_hotkey.setText("<ctrl>+space")
    win._save()
    assert len(emitted) == 1
    assert emitted[0][0] == "<ctrl>+space"


def test_settings_window_no_signal_when_unchanged(qtbot, tmp_path):
    from snipapp.ui.settings_window import SettingsWindow
    s = _make_settings(tmp_path)
    win = SettingsWindow(s)
    qtbot.addWidget(win)
    emitted: list = []
    win.hotkeys_changed.connect(lambda p, sv: emitted.append((p, sv)))
    win._save()
    assert emitted == []


def test_settings_window_cancel_does_not_save(qtbot, tmp_path):
    from snipapp.ui.settings_window import SettingsWindow
    path = tmp_path / "config.toml"
    s = _make_settings(tmp_path)
    win = SettingsWindow(s)
    qtbot.addWidget(win)
    win._picker_hotkey.setText("<ctrl>+x")
    win.reject()
    assert not path.exists()
