"""Fella's memory. Local only. Two parts:
  - profile.txt : a human-readable file the user can open, edit, or delete
  - memory.db   : SQLite log of conversations
Transparency by design: the user owns and can read everything here.
"""

import sqlite3
from pathlib import Path
from datetime import datetime

DATA_DIR = Path.home() / ".local" / "share" / "fella"
DATA_DIR.mkdir(parents=True, exist_ok=True)
PROFILE = DATA_DIR / "profile.txt"
DB = DATA_DIR / "memory.db"


def _db():
    con = sqlite3.connect(DB)
    con.execute(
        "CREATE TABLE IF NOT EXISTS messages "
        "(id INTEGER PRIMARY KEY, ts TEXT, role TEXT, content TEXT)"
    )
    return con


def load_profile() -> str:
    if PROFILE.exists():
        return PROFILE.read_text()
    default = (
        "# Fella's memory about you\n"
        "# You can edit or delete anything here. It never leaves this computer.\n\n"
        "name: (not set yet)\n"
        "notes:\n"
    )
    PROFILE.write_text(default)
    return default


def set_name(name: str):
    text = load_profile()
    lines = []
    for line in text.splitlines():
        if line.startswith("name:"):
            lines.append(f"name: {name}")
        else:
            lines.append(line)
    PROFILE.write_text("\n".join(lines) + "\n")


def get_name() -> str:
    for line in load_profile().splitlines():
        if line.startswith("name:"):
            val = line.split(":", 1)[1].strip()
            return "" if val.startswith("(") else val
    return ""


def log(role: str, content: str):
    con = _db()
    con.execute(
        "INSERT INTO messages (ts, role, content) VALUES (?, ?, ?)",
        (datetime.now().isoformat(timespec="seconds"), role, content),
    )
    con.commit()
    con.close()


def recent(limit: int = 12) -> list[dict]:
    con = _db()
    rows = con.execute(
        "SELECT role, content FROM messages ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    con.close()
    return [{"role": r, "content": c} for r, c in reversed(rows)]


def wipe():
    if DB.exists():
        DB.unlink()
    if PROFILE.exists():
        PROFILE.unlink()
