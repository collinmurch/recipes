"""Markdown for people: recipes, shopping lists, and tables."""

from __future__ import annotations

from .collection import amounts_of, factor, ingredient_line
from .units import describe
from .vocab import humanize


def duration(minutes: int | None) -> str:
    """45 -> "45 min", 150 -> "2 hr 30 min"."""
    if not minutes:
        return ""
    hours, rest = divmod(minutes, 60)
    return " ".join([f"{hours} hr"] * bool(hours) + [f"{rest} min"] * bool(rest))


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
            out.append(f"- {ingredient_line(item, amount)}")
        out.append("")
    if r["cookware"]:
        out += ["## Cookware", "", ", ".join(r["cookware"]), ""]

    out += ["## Steps", ""]
    for section in r["sections"]:
        if section["name"]:
            out += [f"### {section['name']}", ""]
        for item in section["content"]:
            out += [f"> {item['text']}" if item["type"] == "note" else f"{item['number']}. {item['text']}", ""]
    return "\n".join(out).rstrip() + "\n"


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
