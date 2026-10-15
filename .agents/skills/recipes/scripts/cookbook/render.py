"""Markdown for people: recipes, shopping lists, and tables."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from fractions import Fraction

from .collection import amounts_of
from .units import Amount, describe, total
from .vocab import Vocab, humanize, normalize


def duration(minutes: int | None) -> str:
    """45 -> "45 min", 150 -> "2 hr 30 min"."""
    if not minutes:
        return ""
    hours, rest = divmod(minutes, 60)
    return " ".join([f"{hours} hr"] * bool(hours) + [f"{rest} min"] * bool(rest))


def factor(recipe: dict, servings: float | None) -> Fraction:
    if not servings or not recipe.get("servings"):
        return Fraction(1)
    return Fraction(str(servings)) / Fraction(str(recipe["servings"]))


def recipe(r: dict, servings: float | None = None) -> str:
    """A recipe as it reads on the site, optionally scaled."""
    scale = factor(r, servings)
    out = [f"# {r.get('title', r['slug'])}", ""]
    if r.get("description"):
        out += [r["description"], ""]

    times = ", ".join(
        t
        for t in (
            r.get("time_active") and f"{duration(r['time_active'])} active",
            r.get("time_total") and f"{duration(r['time_total'])} total",
        )
        if t
    )
    serves = r.get("servings") and f"serves {servings or r['servings']}" + (
        f" (scaled from {r['servings']})" if scale != 1 else ""
    )
    out.append(
        " · ".join(
            str(x)
            for x in (
                r.get("course"),
                r.get("cuisine"),
                serves,
                times,
                r.get("leftovers") and f"leftovers {r['leftovers']}",
                r.get("rating") and f"{r['rating']}/5",
            )
            if x
        )
    )
    details = [
        x
        for x in (
            r.get("tags") and "tags: " + ", ".join(r["tags"]),
            r.get("proteins") and "protein: " + ", ".join(r["proteins"]),
            r.get("pairs") and "pairs with: " + ", ".join(r["pairs"]),
            r.get("last_cooked") and f"last cooked {r['last_cooked']}",
            r.get("source") and f"source: {r['source']}",
        )
        if x
    ]
    if details:
        out.append(" · ".join(details))

    out += ["", "## Ingredients", ""]
    for group in r["ingredients"]:
        if group["section"]:
            out += [f"**{group['section']}**", ""]
        for item in group["items"]:
            amount = describe(a.scaled(scale) for a in amounts_of(item))
            extra = ", ".join(x for x in (item["note"], item["optional"] and "optional") if x)
            line = " ".join(x for x in (amount, item["text"]) if x)
            out.append(f"- {line}" + (f" ({extra})" if extra else ""))
        out.append("")
    if r["cookware"]:
        out += ["## Cookware", "", ", ".join(r["cookware"]), ""]

    out += ["## Steps", ""]
    for section in r["sections"]:
        if section["name"]:
            out += [f"### {section['name']}", ""]
        for item in section["content"]:
            out += [f"> {item['text']}" if item["type"] == "note" else f"{item['number']}. {step_text(item)}", ""]
    return "\n".join(out).rstrip() + "\n"


def step_text(step: dict) -> str:
    """A step's words as they read on the page."""
    parts = []
    for token in step["tokens"]:
        if token["type"] == "text":
            parts.append(token["value"])
        elif token["type"] == "timer":
            parts.append(token["amount"])
        else:
            parts.append(token["text"])
    return "".join(parts).strip()


@dataclass
class Line:
    name: str
    section: str
    amounts: list[Amount] = field(default_factory=list)
    recipes: list[str] = field(default_factory=list)
    optional: bool = True

    def to_json(self) -> dict:
        amounts = [a for a in total(self.amounts) if a]
        return {"name": self.name, "amount": describe(amounts), "recipes": self.recipes, "optional": self.optional}


def groceries(picks: list[tuple[dict, float | None]], vocab: Vocab, extras: Iterable[str] = ()) -> list[dict]:
    """One shopping list for (recipe, servings) picks plus free-form extras,
    grouped by section in store order. Unknown names land in "other"."""
    lines: dict[str, Line] = {}

    def add(key, name, section, optional, amounts=(), recipe=None):
        line = lines.setdefault(key, Line(name, section))
        line.amounts += amounts
        line.optional = line.optional and optional
        if recipe and recipe not in line.recipes:
            line.recipes.append(recipe)

    for r, servings in picks:
        scale = factor(r, servings)
        for group in r["ingredients"]:
            for item in group["items"]:
                entry = vocab.entries.get(item["name"]) if item["name"] else None
                key = item["name"] or normalize(item["text"])
                amounts = [a.scaled(scale) for a in amounts_of(item)]
                add(key, key, entry.section if entry else "other", item["optional"], amounts, r["slug"])
    for extra in extras:
        entry = vocab.lookup(extra)
        add(
            entry.name if entry else normalize(extra),
            entry.name if entry else extra,
            entry.section if entry else "other",
            False,
        )

    order = [s.name for s in vocab.sections] + ["other"]
    staples = {s.name for s in vocab.sections if s.staple}
    by_name = sorted(lines.values(), key=lambda line: line.name)
    sections = [(name, [line.to_json() for line in by_name if line.section == name]) for name in order]
    return [{"name": name, "staple": name in staples, "items": items} for name, items in sections if items]


def grocery_list(sections: list[dict], title: str) -> str:
    """A shopping list as a Markdown checklist, with staples at the end."""
    out = [f"# {title}", ""]
    for section in (s for s in sections if not s["staple"]):
        out += [f"## {humanize(section['name'])}", ""]
        for item in section["items"]:
            amount = f" — {item['amount']}" if item["amount"] else ""
            optional = " (optional)" if item["optional"] else ""
            shared = f" · {', '.join(item['recipes'])}" if len(item["recipes"]) > 1 else ""
            out.append(f"- [ ] {humanize(item['name'])}{amount}{optional}{shared}")
        out.append("")
    staples = [s for s in sections if s["staple"]]
    if staples:
        out += ["## On hand", "", "Check these before you go:", ""]
        out += [f"- {humanize(s['name'])}: " + ", ".join(humanize(i["name"]) for i in s["items"]) for s in staples]
    return "\n".join(out).rstrip() + "\n"


def table(headers: list[str], rows: list[list]) -> str:
    def cell(value) -> str:
        return "" if value is None else str(value).replace("|", "\\|")

    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines += ["| " + " | ".join(cell(v) for v in row) + " |" for row in rows]
    return "\n".join(lines) + "\n"
