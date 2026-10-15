"""The documented index format (references/index.schema.json) matches what builds produce."""

import json

import pytest
from jsonschema import Draft202012Validator

from conftest import REPO
from cookbook.collection import load_repo, step_text

SCHEMA = json.loads((REPO / ".agents/skills/recipes/references/index.schema.json").read_text())
VALIDATOR = Draft202012Validator(SCHEMA)

VOCAB = """produce:
  lime: {}
  scallion: {aka: [green onion]}

meat:
  pork-shoulder: {protein: pork}

pantry:
  salt: {}

bar:
  rye: {aka: [rye whiskey]}
"""

EVERYTHING = """---
title: Everything Tacos
description: Uses every feature of the format.
course: main
cuisine: mexican
servings: 4
time_active: 20
time_total: 90
leftovers: great
tags: [weekend]
rating: 5
source: https://example.com/tacos
pairs: [manhattan]
---

> Start the pork first.

Season @pork shoulder{1%kg}(cubed) with @salt{=1%tsp}. Rest ~rest{10%minutes}.

== Garnish ==

Slice @green onions{2-3} and @?limes{2}(in wedges) in a #bowl{}. Wait ~{5%min}. Add @salt{%pinch}.
"""

MANHATTAN = """---
title: Manhattan
course: drink
servings: 1
---

Stir @rye whiskey{2%oz}.
"""

PLAN = """---
title: Taco week
spent: 82.5
extras: [paper towels]
meals:
  - recipe: everything-tacos
    date: 2026-10-13
    servings: 6
    cooked: 2026-10-13
    note: Doubled the lime.
---

Notes.
"""


@pytest.fixture
def full_index(make_repo):
    root = make_repo(
        {
            "recipes/everything-tacos.cook": EVERYTHING,
            "drinks/manhattan.cook": MANHATTAN,
            "plans/2026-10-12.md": PLAN,
            "plans/2026-12-24-party.md": "---\nmeals: []\n---\n",
        },
        VOCAB,
    )
    index, _, problems = load_repo(root)
    assert [str(p) for p in problems if p.level == "error"] == []
    return index


def errors(instance) -> list[str]:
    return [f"{'/'.join(map(str, e.absolute_path))}: {e.message}" for e in VALIDATOR.iter_errors(instance)]


def properties(name: str) -> set[str]:
    return set(SCHEMA["$defs"][name]["properties"])


def walk(node, path="#"):
    """Yields (path, schema) for every property schema in the document."""
    if isinstance(node, dict):
        for key, child in node.get("properties", {}).items():
            yield f"{path}/{key}", child
        for key, child in node.items():
            yield from walk(child, f"{path}/{key}")
    elif isinstance(node, list):
        for i, child in enumerate(node):
            yield from walk(child, f"{path}/{i}")


def test_the_schema_is_valid():
    Draft202012Validator.check_schema(SCHEMA)


def test_every_field_is_described():
    undocumented = [path for path, child in walk(SCHEMA) if "description" not in child]
    assert undocumented == []


def test_the_real_collection_matches_the_schema():
    index, _, _ = load_repo(REPO)
    assert errors(index) == []


def test_a_build_using_every_feature_matches_the_schema(full_index):
    assert errors(full_index) == []


def test_every_recipe_field_is_produced(full_index):
    produced = set().union(*(r.keys() for r in full_index["recipes"]))
    assert produced == properties("recipe")


def test_every_plan_and_meal_field_is_produced(full_index):
    plan = next(p for p in full_index["plans"] if p["id"] == "2026-10-12")
    assert set(plan) == properties("plan")
    assert set(plan["meals"][0]) == properties("meal")


def test_every_amount_field_is_produced(full_index):
    amounts = [a for g in full_index["recipes"][0]["ingredients"] for i in g["items"] for a in i["amounts"]]
    assert set().union(*(a.keys() for a in amounts)) == properties("amount")


def test_every_vocab_field_is_produced(full_index):
    entries = [e for s in full_index["vocab"] for e in s["items"]]
    assert set().union(*(e.keys() for e in entries)) == properties("vocabEntry")


def test_undocumented_fields_are_rejected(full_index):
    full_index["recipes"][0]["calories"] = 500
    assert errors(full_index) == ["recipes/0: Additional properties are not allowed ('calories' was unexpected)"]


def test_step_text_is_its_tokens_joined(full_index):
    for recipe in full_index["recipes"]:
        for section in recipe["sections"]:
            for item in section["content"]:
                if item["type"] == "step":
                    assert item["text"] == step_text(item["tokens"])


def test_display_strings_read_naturally(full_index):
    tacos = full_index["recipes"][0]
    lines = [i["line"] for g in tacos["ingredients"] for i in g["items"]]
    assert lines == [
        "1 kg pork shoulder (cubed)",
        "1 tsp salt",
        "2-3 green onions",
        "2 limes (in wedges, optional)",
        "pinch salt",
    ]
    assert tacos["sections"][0]["content"][1]["text"] == "Season pork shoulder with salt. Rest 10 minutes."
