"""Tests for snipapp.core.run_at_login."""

from __future__ import annotations

import platform
from pathlib import Path
from unittest.mock import patch

import pytest

from snipapp.core.run_at_login import (
    _executable,
    get_run_at_login,
    set_run_at_login,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _patch_home(tmp_path):
    """Context manager: redirect Path.home() to tmp_path."""
    return patch("snipapp.core.run_at_login.Path.home", return_value=tmp_path)


# ---------------------------------------------------------------------------
# macOS tests
# ---------------------------------------------------------------------------

@pytest.mark.skipif(platform.system() != "Darwin", reason="macOS only")
class TestMacOS:
    def test_enable_creates_plist(self, tmp_path):
        with _patch_home(tmp_path):
            set_run_at_login(True)
        plist = tmp_path / "Library" / "LaunchAgents" / "com.bytesnip.app.plist"
        assert plist.exists()
        assert "<key>RunAtLoad</key>" in plist.read_text()

    def test_plist_contains_executable(self, tmp_path):
        with _patch_home(tmp_path):
            set_run_at_login(True)
        plist = tmp_path / "Library" / "LaunchAgents" / "com.bytesnip.app.plist"
        content = plist.read_text()
        assert _executable() in content

    def test_disable_removes_plist(self, tmp_path):
        with _patch_home(tmp_path):
            set_run_at_login(True)
            set_run_at_login(False)
        plist = tmp_path / "Library" / "LaunchAgents" / "com.bytesnip.app.plist"
        assert not plist.exists()

    def test_disable_when_not_enabled_is_noop(self, tmp_path):
        with _patch_home(tmp_path):
            set_run_at_login(False)  # nothing to remove — should not raise

    def test_get_returns_true_when_plist_exists(self, tmp_path):
        with _patch_home(tmp_path):
            set_run_at_login(True)
            assert get_run_at_login() is True

    def test_get_returns_false_when_no_plist(self, tmp_path):
        with _patch_home(tmp_path):
            assert get_run_at_login() is False


# ---------------------------------------------------------------------------
# Linux tests
# ---------------------------------------------------------------------------

@pytest.mark.skipif(platform.system() == "Darwin", reason="Linux only")
class TestLinux:
    def test_enable_creates_desktop_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
        set_run_at_login(True)
        desktop = tmp_path / ".config" / "autostart" / "bytesnip.desktop"
        assert desktop.exists()
        assert "ByteSnip" in desktop.read_text()

    def test_disable_removes_desktop_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
        set_run_at_login(True)
        set_run_at_login(False)
        desktop = tmp_path / ".config" / "autostart" / "bytesnip.desktop"
        assert not desktop.exists()

    def test_get_returns_true_when_desktop_exists(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
        set_run_at_login(True)
        assert get_run_at_login() is True


# ---------------------------------------------------------------------------
# Cross-platform
# ---------------------------------------------------------------------------

def test_executable_returns_string():
    exe = _executable()
    assert isinstance(exe, str)
    assert len(exe) > 0
