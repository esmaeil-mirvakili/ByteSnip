# ByteSnip

A fast, keyboard-first code snippet manager for macOS and Linux. Runs in the background — press a hotkey to instantly browse, search, and copy snippets, or save any selected text as a new snippet.

## Hotkeys

| Shortcut | Action |
| --- | --- |
| `Cmd+Shift+`` ` | Open snippet picker |
| `Ctrl+Cmd+C` | Save selected text as a snippet |

## Install

Download the latest `ByteSnip-vX.X.X.dmg` from the [Releases](../../releases) page, open it, and drag **ByteSnip.app** to your Applications folder.

### macOS permissions

Grant these in **System Settings → Privacy & Security** after first launch:

- **Accessibility** — for global hotkeys and selected-text capture
- **Input Monitoring** — for listening to key events

Restart the app after granting permissions.

## Usage

ByteSnip runs in the background with a menu-bar icon. No Dock entry.

**Picker** (`Cmd+Shift+`` `)
Browse folders and snippets, type to fuzzy-search, press `Enter` to copy to clipboard. Press `E` to edit the selected snippet, `Del` to delete it.

**Save** (`Ctrl+Cmd+C`)
Select text in any app, press the hotkey. ByteSnip captures it, auto-detects the language, and opens a form to set the title, folder, tags, and description before saving.

**Settings**
Click the menu-bar icon → Settings to remap hotkeys, toggle search-in-body, and enable run-at-login.

## Development

Requirements: Python 3.11+, macOS 12+ or Linux (X11).

```bash
git clone https://github.com/yourname/bytesnip.git
cd bytesnip
pip install -e ".[dev,macos]"   # macOS
pip install -e ".[dev,linux]"   # Linux
```

| Command | Description |
| --- | --- |
| `make test` | Run tests |
| `make lint` | Ruff + mypy |
| `make build` | Build `dist/ByteSnip.app` via PyInstaller |
| `make dmg` | Full clean build + create `dist/ByteSnip-vX.X.X.dmg` |
| `make reset-db` | Wipe all snippets, folders, and tags |

Releases are published automatically via GitHub Actions when a tag is pushed:

```bash
git tag v0.1.0
git push origin v0.1.0
```

## License

See [LICENSE](LICENSE).
