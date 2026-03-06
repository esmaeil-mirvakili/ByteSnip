# Project: ByteSnip (Python cross-platform snippet manager)

A desktop code snippet manager written in Python for macOS and Linux. It runs in the background and provides two global shortcuts:

* **Command + Shift + `**: open a fast “snippet picker” to browse folders/snippets with a syntax-highlighted preview. Selecting an item (or pressing Enter) copies it to the clipboard and closes the picker.
* **Control + Command + C**: open a “save snippet” window that captures the currently selected text (from the active app), lets the user choose folder, tags, and language (auto-detected), shows a syntax-highlighted preview, then saves it.

The app is optimized for speed: instant open, keyboard-first navigation, fuzzy search, minimal clicks.

---

## Python Env

use the conda env for the project: conda activate bytesnip

---

## Edit steps

* do the edit
* write tests for the edit
* run the test to make sure it works

---

## Core user flows

### 1) Browse and copy snippets (Cmd+Shift+`)

1. User presses **Cmd+Shift+`**.
2. A small, centered window appears (spotlight-style).
3. Left side: folders/snippets list with search box.
4. Right side: preview pane with syntax highlighting.
5. User navigates with arrows, types to filter, presses **Enter**.
6. Snippet text is copied to clipboard.
7. Window closes.

### 2) Save a new snippet (Ctrl+Cmd+C)

1. User selects code/text in any app.
2. User presses **Ctrl+Cmd+C**.
3. App opens “Save snippet” window.
4. The selected text is captured and pre-filled.
5. Language is auto-detected; if confidence is low, use `text`.
6. Preview pane highlights using chosen language.
7. User sets:

   * Title (optional but recommended)
   * Folder
   * Tags
   * Language (override allowed)
   * Description
8. User presses **Save**.
9. Snippet is stored and becomes searchable immediately.

---

## Requirements

### Functional requirements

* Global hotkeys:

  * Cmd+Shift+` and Ctrl+Cmd+C
* Fast searchable list:

  * Fuzzy search by title, tags, folder, language, snippet body (optional configurable)
* Folder hierarchy:

  * Folders can contain snippets and subfolders
* Preview:

  * Syntax-highlighted preview of snippet using detected/selected language
  * Support plain text fallback
* Copy:

  * Selecting a snippet copies raw snippet body to clipboard
* Save snippet:

  * Capture selected text from the currently focused application
  * Tag editor with autocomplete
  * Folder picker
  * Language selector + auto-detect
* Data persistence:

  * Local database (SQLite) storing snippets, folders, tags, metadata
* Import/Export:

  * Export to JSON (and optionally Markdown)
  * Import from JSON
* Settings:

  * Hotkey remapping
  * Theme (light/dark)
  * Default folder
  * Whether to search inside snippet bodies
* Runs at login (optional)

### Non-functional requirements

* Opens in under ~150ms on a typical dev machine (target)
* Keyboard-first UX; mouse optional
* Works offline
* Robust against large libraries (10k+ snippets)
* No telemetry

---

## Suggested tech stack (Python)

### UI

* **Qt for Python (PySide6)** for cross-platform desktop UI and good performance.
* Use a “spotlight-style” frameless window for picker.

### Global hotkeys

* **pynput** or **keyboard** (Linux caveats), but for reliability:

  * macOS: consider bridging to Quartz event taps if needed (via `pyobjc`) for precise hotkeys.
  * Linux: X11 vs Wayland differences. Prefer:

    * X11: `python-xlib` or `keyboard`
    * Wayland: may require desktop-portal limitations; provide fallback (tray menu open) if hotkeys are blocked.

### Clipboard

* Use Qt clipboard via `QApplication.clipboard()` for consistent behavior.

### Syntax highlighting

Options:

* **Pygments** for tokenizing + render as HTML, then display in Qt via `QTextBrowser` or `QWebEngineView`.
* For best rendering and speed, start with `QTextDocument` + HTML from Pygments.
* Later upgrade to embedded Monaco/CodeMirror in a webview if desired.

### Language detection

* Use **Pygments lexers guess** (`pygments.lexers.guess_lexer`) with guardrails:

  * If confidence low or exception: `text`
  * Allow manual override in UI
* Optional later: integrate `enry` (GitHub Linguist) via subprocess for better accuracy, but keep MVP pure Python.

### Storage

* **SQLite** + a thin data layer:

  * Either raw `sqlite3` + queries, or `SQLAlchemy` if you want ORM.
* FTS:

  * Use SQLite FTS5 for fast searching (title/tags/body).

### Capturing selected text

Hard truth: “get selected text from any app” is OS-specific and not fully reliable everywhere.

* macOS:

  * Use Accessibility API (AX) via `pyobjc` for selected text retrieval where possible.
  * Fallback approach: simulate Cmd+C, read clipboard, then restore clipboard (with user opt-in because it’s intrusive).
* Linux:

  * X11: can read PRIMARY selection in many apps; also can simulate Ctrl+C.
  * Wayland: selection capture is restricted; likely need clipboard simulation fallback.

MVP should implement **clipboard-simulation fallback** with a safe restore mechanism.

---

## Architecture

### Process model

* Single background process with:

  * System tray icon (optional but recommended)
  * Hotkey listener
  * Windows: Snippet Picker + Save Snippet dialog (created on demand)

### Modules

* `app/`

  * `main.py` bootstrap Qt app + tray + hotkeys
* `ui/`

  * `picker_window.py` spotlight picker with list + preview
  * `save_window.py` dialog with fields + preview
  * `components/` reusable widgets (tag input, folder tree, code preview)
* `core/`

  * `db.py` SQLite connection + migrations
  * `models.py` snippet/folder/tag dataclasses or ORM models
  * `search.py` FTS + fuzzy matching
  * `clipboard.py` copy/paste helpers + clipboard restore
  * `hotkeys.py` OS-specific hotkey binding
  * `capture.py` selected-text capture (OS adapters)
  * `highlight.py` pygments highlighting + lexer detection
  * `settings.py` config storage (toml/json) and defaults
* `tests/`

  * Unit tests for db/search/highlight/detection

### Data model (SQLite)

* `folders(id, parent_id, name, created_at, updated_at)`
* `snippets(id, folder_id, title, body, language, created_at, updated_at, last_used_at, use_count)`
* `tags(id, name)`
* `snippet_tags(snippet_id, tag_id)`
* FTS virtual table (optional):

  * `snippets_fts(title, body, tags_text, folder_path, content='snippets', content_rowid='id')`

---

## UI behavior details

### Picker window

* Opens centered, always-on-top, no taskbar entry.
* Components:

  * Search input (auto-focused)
  * List view:

    * Supports folder navigation (left/right arrows or Enter to open folder)
    * Shows snippet title and small metadata (language, tags count)
  * Preview pane:

    * Renders highlighted HTML
    * Shows language badge and tags
* Keys:

  * Up/Down: move selection
  * Enter: copy snippet (if snippet selected) or enter folder (if folder selected)
  * Esc: close
  * Backspace: go up folder when search box empty (optional)
  * Cmd/Ctrl+F: focus search (optional)

### Save snippet window

* Opens centered; fields:

  * Title (defaults to first line trimmed, or “Untitled”)
  * Folder picker (tree)
  * Tags input (type, hit Enter to add, shows chips)
  * Language dropdown (auto-detected pre-selected)
  * Code editor / text area (editable)
  * Preview pane (optional toggle, or always visible)
* Buttons:

  * Save
  * Cancel
* Keys:

  * Cmd/Ctrl+Enter: Save
  * Esc: Cancel

---

## MVP scope (recommended)

1. Local-only storage
2. Picker window: folder tree + snippet list + search + preview + copy
3. Save window: capture selected text via clipboard-sim fallback + tags/folder/language + save
4. Pygments highlight
5. SQLite + simple migrations

Defer:

* Cloud sync
* Team sharing
* Full offline export formats beyond JSON
* Advanced language detection beyond Pygments
* Wayland-native selection capture

---

## Packaging and install

### macOS

* Use `pyinstaller` to build an app bundle.
* Sign/notarize for smooth install (later).
* Accessibility permissions may be needed for selection capture and hotkeys.

### Linux

* Provide AppImage (easiest), or .deb/.rpm.
* Note Wayland hotkey constraints: document limitations and provide tray/menu fallback.

---

## Edge cases and constraints (be honest)

* Capturing selected text is not universally reliable without OS permissions and sometimes not possible on Wayland without clipboard simulation.
* Global hotkeys may conflict with system/app shortcuts; provide a UI to remap.
* Syntax highlighting for very large snippets should be throttled or deferred to avoid UI lag.

---

## Acceptance criteria

* Pressing **Cmd+Shift+`** shows picker, user can search, preview highlights correctly, Enter copies snippet.
* Pressing **Ctrl+Cmd+C** opens save window and pre-fills with selected text (via capture method), language auto-detected or `text`.
* Snippets persist across restarts.
* Search returns results quickly (under 50ms for 1k snippets target).
* Works on macOS and at least one mainstream Linux desktop on X11.

---

## Development notes

* Prioritize keyboard UX and fast render paths.
* Add logging with rotating file handler for debugging hotkey/capture issues.
* Write a small migration system for SQLite schema updates.
* Ensure clipboard restore logic is safe: store previous clipboard contents and restore after capture unless user opts out.

---

## Suggested repo structure

```
README.md
CLAUDE.md
pyproject.toml
src/snipapp/
main.py
app/
ui/
core/
tests/
assets/
```
