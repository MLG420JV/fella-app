"""Flathub fallback for apps that aren't in Fella's curated pacman catalog
(fella/apps.py). If you ask to install something Fella doesn't recognize by
name, it searches the same Flathub app listing KDE Discover uses and offers
the closest match - still through the normal confirm-button and snapshot
safety flow, never installing anything without a click.

`flatpak search` reads the locally cached appstream metadata for configured
remotes, so this doesn't need a network round-trip just to search; only an
actual install does (same as it would through Discover).
"""

import json
import re
import shutil
import subprocess

from .recipes import Recipe

_INTENT_RE = re.compile(r"\b(?:install|get me|download|set up|setup)\b\s+(?:the\s+)?(.+)", re.I)
_TRAILING_RE = re.compile(r"\s+(?:for me|please|now)\s*$", re.I)


def available() -> bool:
    return bool(shutil.which("flatpak"))


def extract_query(text: str) -> str | None:
    """Pull the app name out of an install request.

    e.g. "can you install spotify for me" -> "spotify"
    """
    m = _INTENT_RE.search(text)
    if not m:
        return None
    query = _TRAILING_RE.sub("", m.group(1)).strip(" ?.!\"'")
    return query or None


def search(query: str, limit: int = 1) -> list[tuple[str, str]]:
    """Return the top Flathub matches as (application_id, name) tuples."""
    try:
        p = subprocess.run(
            ["flatpak", "search", "-j", query],
            capture_output=True, text=True, timeout=10,
        )
        results = json.loads(p.stdout or "[]")
    except (subprocess.SubprocessError, ValueError, OSError):
        return []
    return [(r["application_id"], r["name"]) for r in results[:limit] if r.get("application_id")]


def install_recipe(app_id: str, title: str) -> Recipe:
    return Recipe({
        "id": f"flatpak_{app_id}",
        "title": f"Install {title} (Flathub)",
        "explain": f"I'll install {title} from Flathub, the same store KDE Discover uses.",
        "commands": [f"flatpak install --system -y flathub {app_id}"],
        "verify": f"flatpak info {app_id}",
        "undo": f"flatpak uninstall --system -y {app_id}",
        "needs_root": True,
    })
