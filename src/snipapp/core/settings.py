"""User-facing settings stored as TOML in the platform config directory."""

from __future__ import annotations

import copy
import logging
import platform
import tomllib
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULTS: dict[str, Any] = {
    "theme": "dark",
    "default_folder_id": None,
    "search_in_body": True,
    "hotkeys": {
        "picker": "<cmd>+<shift>+`",
        "save": "<ctrl>+<cmd>+c",
    },
    "run_at_login": False,
}


def get_config_path() -> Path:
    if platform.system() == "Darwin":
        base = Path.home() / "Library" / "Application Support" / "ByteSnip"
    else:
        import os
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "bytesnip"
    base.mkdir(parents=True, exist_ok=True)
    return base / "config.toml"


class Settings:
    """Thin wrapper around a TOML config file with in-memory defaults."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or get_config_path()
        self._data: dict[str, Any] = copy.deepcopy(_DEFAULTS)
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                with self._path.open("rb") as fh:
                    loaded = tomllib.load(fh)
                _deep_merge(self._data, loaded)
                logger.debug("Loaded settings from %s", self._path)
            except Exception as exc:
                logger.warning("Could not load settings (%s); using defaults.", exc)

    def save(self) -> None:
        try:
            import tomli_w  # optional write dependency
            with self._path.open("wb") as fh:
                tomli_w.dump(self._data, fh)
        except ImportError:
            # Fallback: write minimal TOML manually
            with self._path.open("w") as fh:
                fh.write(_dict_to_toml(self._data))
        logger.debug("Saved settings to %s", self._path)

    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split(".")
        node: Any = self._data
        for k in keys:
            if not isinstance(node, dict):
                return default
            node = node.get(k, default)
        return node

    def set(self, key: str, value: Any) -> None:
        keys = key.split(".")
        node = self._data
        for k in keys[:-1]:
            node = node.setdefault(k, {})
        node[keys[-1]] = value


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> None:
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v


def _dict_to_toml(d: dict[str, Any], prefix: str = "") -> str:
    """Write *d* as TOML, emitting all scalar keys before any sub-tables.

    This ensures that top-level scalars are never accidentally placed inside a
    previously opened ``[section]`` header.
    """
    scalar_lines: list[str] = []
    table_lines: list[str] = []

    for k, v in d.items():
        if isinstance(v, dict):
            section = f"{prefix}.{k}" if prefix else k
            table_lines.append(f"\n[{section}]")
            table_lines.append(_dict_to_toml(v, prefix=section))
        elif isinstance(v, bool):
            scalar_lines.append(f"{k} = {'true' if v else 'false'}")
        elif isinstance(v, str):
            # Escape backslashes and double-quotes inside TOML basic strings
            escaped = v.replace("\\", "\\\\").replace('"', '\\"')
            scalar_lines.append(f'{k} = "{escaped}"')
        elif v is None:
            scalar_lines.append(f"# {k} =")
        else:
            scalar_lines.append(f"{k} = {v!r}")

    return "\n".join(scalar_lines + table_lines)
