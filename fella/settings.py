"""Fella's user-editable settings (avatar colors, more later). Local-only
JSON file, same spirit as memory.py - you can open, edit, or delete it and
nothing leaves this computer.
"""

import json
from pathlib import Path

DATA_DIR = Path.home() / ".local" / "share" / "fella"
DATA_DIR.mkdir(parents=True, exist_ok=True)
SETTINGS_FILE = DATA_DIR / "settings.json"

DEFAULT_BODY = "#A79FF0"
DEFAULT_EYE = "#26215C"


def load() -> dict:
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save(data: dict):
    try:
        SETTINGS_FILE.write_text(json.dumps(data, indent=2))
    except OSError:
        pass


def get_colors() -> tuple[str, str]:
    data = load()
    return data.get("body", DEFAULT_BODY), data.get("eye", DEFAULT_EYE)


def set_colors(body: str, eye: str):
    data = load()
    data["body"] = body
    data["eye"] = eye
    save(data)
