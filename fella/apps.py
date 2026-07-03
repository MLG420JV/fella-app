"""Catalog of apps Fella can install on request, e.g. "install steam".

Fella never runs pacman with raw user-typed text - it only ever installs
a package from this fixed catalog, the same way recipes.py only ever runs
commands from its YAML files. This keeps "install X" as safe as the rest
of Fella's actions: preview -> snapshot -> execute -> verify, with a
button the user has to click.
"""

import re

from .recipes import Recipe

# key -> title, real pacman/AUR package name (chaotic-aur covers AUR here),
# a binary to verify against, and any extra phrases users might say.
APPS = {
    "steam":     {"title": "Steam",                  "package": "steam",                    "aliases": []},
    "discord":   {"title": "Discord",                "package": "discord",                  "aliases": []},
    "spotify":   {"title": "Spotify",                "package": "spotify",                  "aliases": []},
    "vscode":    {"title": "VS Code",                "package": "code",                     "aliases": ["visual studio code", "vs code"]},
    "gimp":      {"title": "GIMP",                   "package": "gimp",                     "aliases": []},
    "blender":   {"title": "Blender",                "package": "blender",                  "aliases": []},
    "obs":       {"title": "OBS Studio",             "package": "obs-studio",               "aliases": ["obs studio"]},
    "vlc":       {"title": "VLC",                    "package": "vlc",                      "aliases": []},
    "telegram":  {"title": "Telegram",               "package": "telegram-desktop",         "aliases": []},
    "lutris":    {"title": "Lutris",                 "package": "lutris",                   "aliases": []},
    "heroic":    {"title": "Heroic Games Launcher",  "package": "heroic-games-launcher-bin", "aliases": ["heroic games launcher"]},
    "timeshift": {"title": "Timeshift",              "package": "timeshift",                "aliases": []},
    "chromium":  {"title": "Chromium",               "package": "chromium",                 "aliases": []},
    "firefox":   {"title": "Firefox",                "package": "firefox",                  "aliases": []},
    "slack":     {"title": "Slack",                  "package": "slack-desktop",            "aliases": []},
}

# Require an install-ish verb so mentioning an app in passing ("my steam
# library is huge") doesn't pop an install button.
_INTENT_RE = re.compile(r"\b(install|get me|download|set up|setup)\b", re.I)


def match_app(text: str):
    """Return (key, info) for the first cataloged app the user asked to install."""
    if not _INTENT_RE.search(text):
        return None
    t = text.lower()
    for key, info in APPS.items():
        for name in [key, *info["aliases"]]:
            if re.search(rf"\b{re.escape(name)}\b", t):
                return key, info
    return None


def install_recipe(key: str) -> Recipe:
    info = APPS[key]
    pkg = info["package"]
    return Recipe({
        "id": f"install_{key}",
        "title": f"Install {info['title']}",
        "explain": f"I'll install {info['title']} ({pkg}) from the package repos.",
        "commands": [f"sudo pacman -S --needed --noconfirm {pkg}"],
        "verify": f"pacman -Qi {pkg}",
        "undo": f"sudo pacman -Rns --noconfirm {pkg}",
        "needs_root": True,
    })


def catalog_hint() -> str:
    """A compact list handed to the model so it knows what it can install."""
    return "\n".join(f"- install_{key}: Install {info['title']}" for key, info in APPS.items())
