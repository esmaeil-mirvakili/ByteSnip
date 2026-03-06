.PHONY: build clean test lint dev-macos dev-linux reset-db

# ── Development ───────────────────────────────────────────────────────────────

dev-macos:
	pip install -e ".[dev,macos]"

dev-linux:
	pip install -e ".[dev,linux]"

test:
	pytest

lint:
	ruff check src/ tests/
	mypy src/

# ── Icons ─────────────────────────────────────────────────────────────────────

icns:
	python scripts/make_icns.py

# ── Build (PyInstaller) ───────────────────────────────────────────────────────

build: icns
	pyinstaller ByteSnip.spec --clean

dmg: clean build
	@which create-dmg > /dev/null || brew install create-dmg
	@mkdir -p dist/dmg_stage && cp -r dist/ByteSnip.app dist/dmg_stage/
	@VERSION=$$(python -c "import importlib.metadata; print(importlib.metadata.version('bytesnip'))") && \
	create-dmg \
	  --volname "ByteSnip" \
	  --window-pos 200 120 \
	  --window-size 600 380 \
	  --icon-size 128 \
	  --icon "ByteSnip.app" 150 185 \
	  --hide-extension "ByteSnip.app" \
	  --app-drop-link 450 185 \
	  "dist/ByteSnip-v$$VERSION.dmg" \
	  "dist/dmg_stage/"
	@hdiutil detach "/Volumes/ByteSnip" 2>/dev/null || true
	@rm -rf dist/dmg_stage
	@echo "Created dist/ByteSnip-v$$VERSION.dmg"

# ── Database ──────────────────────────────────────────────────────────────────

reset-db:
	python scripts/reset_db.py

# ── Clean ─────────────────────────────────────────────────────────────────────

clean:
	rm -rf build/ dist/
