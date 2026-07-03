"""Loads repair recipes (YAML) and runs them through the safety gate:
preview -> snapshot -> execute -> verify. The AI picks recipes; it never
invents raw commands. This is what keeps Fella safe for beginners.
"""

import re
import subprocess
from pathlib import Path
import yaml

RECIPE_DIR = Path(__file__).resolve().parent.parent / "recipes"


class Recipe:
    def __init__(self, data: dict):
        self.id = data["id"]
        self.title = data["title"]
        self.explain = data["explain"]
        self.commands = data.get("commands", [])
        self.verify = data.get("verify", "")
        self.undo = data.get("undo", "")
        self.needs_root = data.get("needs_root", False)


def load_recipes() -> dict[str, Recipe]:
    recipes = {}
    for f in sorted(RECIPE_DIR.glob("*.yaml")):
        data = yaml.safe_load(f.read_text())
        recipes[data["id"]] = Recipe(data)
    return recipes


def recipe_hint(recipes: dict[str, Recipe]) -> str:
    """A compact list handed to the model so it knows what it can fix."""
    return "\n".join(f"- {r.id}: {r.title}" for r in recipes.values())


def _run(cmd: str) -> tuple[int, str]:
    # Recipes are authored with `sudo` for readability, but run via `pkexec`
    # so the password prompt is a real KDE dialog in front of Fella instead
    # of going to whatever terminal's stdin happens to be behind the window.
    cmd = re.sub(r"\bsudo\b", "pkexec", cmd)
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr).strip()


def make_snapshot(label: str) -> bool:
    """Best-effort restore point. Uses snapper if present (Garuda ships it)."""
    code, _ = _run(f'command -v snapper && sudo snapper create -d "Fella: {label}"')
    return code == 0


def run_recipe(recipe: Recipe, do_snapshot: bool = True):
    """Generator yielding human-readable progress lines."""
    if do_snapshot:
        yield "Making a restore point first..."
        ok = make_snapshot(recipe.title)
        yield "Restore point ready." if ok else "(Couldn't make a restore point - continuing carefully.)"

    for cmd in recipe.commands:
        yield f"Running: {cmd}"
        code, out = _run(cmd)
        if code != 0:
            yield f"That step had a problem: {out[:400]}"
            yield "Stopping here so nothing gets worse. You can undo if needed."
            return

    if recipe.verify:
        code, _ = _run(recipe.verify)
        yield "Fixed and verified!" if code == 0 else "Ran the fix, but I couldn't confirm it worked. Keep an eye on it."
    else:
        yield "Done!"
