"""Cross-checks the parser against the reference `cook` CLI when it's installed.

CI doesn't install it, so these run locally only.
"""

import json
import shutil
import subprocess

import pytest

from conftest import REPO
from cookbook.cooklang import Cookware, Ingredient, Note, Timer, parse

FILES = sorted(
    p.relative_to(REPO).as_posix() for folder in ("recipes", "drinks") for p in (REPO / folder).glob("*.cook")
)

pytestmark = pytest.mark.skipif(shutil.which("cook") is None, reason="cook CLI not installed")


def value(quantity):
    if quantity is None:
        return None
    if quantity.numeric:
        return float(quantity.value)
    return quantity.text


def ours(path: str) -> dict:
    recipe = parse((REPO / path).read_text())
    tokens = recipe.tokens
    return {
        "ingredients": [
            (
                t.name,
                value(t.amount.quantity) if t.amount else None,
                t.amount.unit if t.amount else None,
                t.note,
                t.optional,
            )
            for t in tokens
            if isinstance(t, Ingredient)
        ],
        "cookware": list(dict.fromkeys(t.name for t in tokens if isinstance(t, Cookware))),
        "timers": [(value(t.amount.quantity), t.amount.unit) for t in tokens if isinstance(t, Timer)],
        "sections": [s.name for s in recipe.sections],
        "notes": [c.text for s in recipe.sections for c in s.content if isinstance(c, Note)],
    }


def reference_value(quantity):
    if quantity is None:
        return None
    v = quantity["value"]
    return float(v["value"]["value"]) if v["type"] == "number" else v["value"]


def theirs(path: str) -> dict:
    out = subprocess.run(
        ["cook", "recipe", str(REPO / path), "--format", "json"], capture_output=True, text=True, check=True
    )
    ref = json.loads(out.stdout)
    return {
        "ingredients": [
            (
                i["name"],
                reference_value(i["quantity"]),
                (i["quantity"] or {}).get("unit"),
                i["note"],
                "OPT" in i["modifiers"],
            )
            for i in ref["ingredients"]
        ],
        "cookware": list(dict.fromkeys(c["name"] for c in ref["cookware"])),
        "timers": [(reference_value(t["quantity"]), t["quantity"]["unit"]) for t in ref["timers"]],
        "sections": [s["name"] for s in ref["sections"]],
        "notes": [c["value"] for s in ref["sections"] for c in s["content"] if c["type"] == "text"],
    }


@pytest.mark.parametrize("path", FILES)
def test_parses_like_cook(path):
    assert ours(path) == theirs(path)
