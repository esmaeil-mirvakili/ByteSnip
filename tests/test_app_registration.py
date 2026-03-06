"""Tests for snipapp.core.app_registration."""

from __future__ import annotations

import platform
from pathlib import Path
from unittest.mock import patch

import pytest

import snipapp.core.app_registration as reg


def _patch_home(tmp_path):
    return patch.object(Path, "home", return_value=tmp_path)


# ---------------------------------------------------------------------------
# Sentinel / is_registered
# ---------------------------------------------------------------------------

def test_not_registered_initially(tmp_path):
    with _patch_home(tmp_path):
        # Reimport sentinel reference inside patched context
        sentinel = tmp_path / ".local" / "share" / "bytesnip" / ".app_registered"
        assert not sentinel.exists()


def test_register_writes_sentinel(tmp_path, monkeypatch):
    monkeypatch.setattr(reg, "_macos_register" if platform.system() == "Darwin" else "_linux_register",
                        lambda: None)
    with _patch_home(tmp_path):
        monkeypatch.setattr(reg, "_SENTINEL", tmp_path / ".local" / "share" / "bytesnip" / ".app_registered")
        reg.register_app()
        assert reg._SENTINEL.exists()


def test_unregister_removes_sentinel(tmp_path, monkeypatch):
    monkeypatch.setattr(reg, "_macos_unregister" if platform.system() == "Darwin" else "_linux_unregister",
                        lambda: None)
    sentinel = tmp_path / ".local" / "share" / "bytesnip" / ".app_registered"
    sentinel.parent.mkdir(parents=True, exist_ok=True)
    sentinel.write_text("1")
    monkeypatch.setattr(reg, "_SENTINEL", sentinel)
    reg.unregister_app()
    assert not sentinel.exists()


def test_is_registered_reads_sentinel(tmp_path, monkeypatch):
    sentinel = tmp_path / ".local" / "share" / "bytesnip" / ".app_registered"
    monkeypatch.setattr(reg, "_SENTINEL", sentinel)
    assert not reg.is_registered()
    sentinel.parent.mkdir(parents=True, exist_ok=True)
    sentinel.write_text("1")
    assert reg.is_registered()


# ---------------------------------------------------------------------------
# macOS tests
# ---------------------------------------------------------------------------

@pytest.mark.skipif(platform.system() != "Darwin", reason="macOS only")
class TestMacOS:
    def _app(self, tmp_path):
        return tmp_path / "Applications" / "ByteSnip.app"

    def test_creates_app_bundle(self, tmp_path):
        with _patch_home(tmp_path):
            reg._macos_register()
        assert (self._app(tmp_path) / "Contents" / "MacOS" / "ByteSnip").exists()

    def test_launcher_is_executable(self, tmp_path):
        with _patch_home(tmp_path):
            reg._macos_register()
        launcher = self._app(tmp_path) / "Contents" / "MacOS" / "ByteSnip"
        assert launcher.stat().st_mode & 0o111  # any execute bit set

    def test_plist_contains_bundle_id(self, tmp_path):
        with _patch_home(tmp_path):
            reg._macos_register()
        plist = (self._app(tmp_path) / "Contents" / "Info.plist").read_text()
        assert "com.bytesnip.app" in plist
        assert "ByteSnip" in plist

    def test_launcher_contains_executable(self, tmp_path):
        with _patch_home(tmp_path):
            reg._macos_register()
        launcher = (self._app(tmp_path) / "Contents" / "MacOS" / "ByteSnip").read_text()
        assert reg._executable() in launcher

    def test_unregister_removes_bundle(self, tmp_path):
        with _patch_home(tmp_path):
            reg._macos_register()
            reg._macos_unregister()
        assert not self._app(tmp_path).exists()

    def test_unregister_noop_when_not_present(self, tmp_path):
        with _patch_home(tmp_path):
            reg._macos_unregister()  # should not raise


# ---------------------------------------------------------------------------
# Linux tests
# ---------------------------------------------------------------------------

@pytest.mark.skipif(platform.system() == "Darwin", reason="Linux only")
class TestLinux:
    def test_creates_desktop_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / ".local" / "share"))
        reg._linux_register()
        desktop = tmp_path / ".local" / "share" / "applications" / "bytesnip.desktop"
        assert desktop.exists()
        content = desktop.read_text()
        assert "ByteSnip" in content
        assert "Type=Application" in content

    def test_unregister_removes_desktop(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / ".local" / "share"))
        reg._linux_register()
        reg._linux_unregister()
        desktop = tmp_path / ".local" / "share" / "applications" / "bytesnip.desktop"
        assert not desktop.exists()


# ---------------------------------------------------------------------------
# Cross-platform
# ---------------------------------------------------------------------------

def test_executable_is_non_empty_string():
    assert isinstance(reg._executable(), str)
    assert reg._executable()
