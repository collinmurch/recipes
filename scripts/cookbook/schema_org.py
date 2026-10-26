"""schema.org Recipe JSON-LD, the standard that recipe apps and search engines read.

Built only from index records, so anything holding index.json could do the same.
Mapping notes:
- There's no schema.org field for active time, so only totalTime is set.
- recipeIngredient is a flat list; ingredient sections don't survive.
- A source URL becomes isBasedOn; a text source ("Grandma") becomes citation.
- The page URL isn't known here; whoever publishes the page adds "url".
"""

from __future__ import annotations

CONTEXT = "https://schema.org"


def recipe(r: dict) -> dict:
    """One index record as a schema.org Recipe."""
    out: dict = {"@context": CONTEXT, "@type": "Recipe", "name": r["title"]}
    optional = {
        "description": r.get("description"),
        "recipeCategory": r.get("course"),
        "recipeCuisine": r.get("cuisine"),
        "keywords": ", ".join(r.get("tags", [])),
        "recipeYield": r.get("servings") and servings(r["servings"]),
        "totalTime": r.get("time_total") and duration(r["time_total"]),
        "tool": r["cookware"],
        "recipeIngredient": [item["line"] for group in r["ingredients"] for item in group["items"]],
        "recipeInstructions": instructions(r["sections"]),
    }
    out.update({key: value for key, value in optional.items() if value})
    if source := r.get("source"):
        out["isBasedOn" if source.startswith(("http://", "https://")) else "citation"] = source
    return out


def graph(records: list[dict]) -> dict:
    """Several recipes as one JSON-LD document."""
    return {"@context": CONTEXT, "@graph": [{k: v for k, v in recipe(r).items() if k != "@context"} for r in records]}


def instructions(sections: list[dict]) -> list[dict]:
    """Steps and notes in order; a named section becomes a HowToSection around its own."""
    out: list[dict] = []
    for section in sections:
        items = [
            {"@type": "HowToStep" if item["type"] == "step" else "HowToTip", "text": item["text"]}
            for item in section["content"]
        ]
        if section["name"]:
            out.append({"@type": "HowToSection", "name": section["name"], "itemListElement": items})
        else:
            out.extend(items)
    return out


def duration(minutes: int) -> str:
    """ISO 8601 duration: 45 -> "PT45M", 150 -> "PT2H30M"."""
    hours, rest = divmod(minutes, 60)
    return "PT" + (f"{hours}H" if hours else "") + (f"{rest}M" if rest else "")


def servings(count: float) -> str:
    number = int(count) if float(count).is_integer() else count
    return f"{number} serving{'' if number == 1 else 's'}"
