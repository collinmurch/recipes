"""The collection: compiling files into index records, checking them, and
loading everything from a repo checkout or from the published index."""

from __future__ import annotations

import gzip
import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from . import cooklang, yamlio
from .cooklang import Cookware, Ingredient, Note, Text, Timer
from .units import Amount, canonical_unit, describe, total, units_json
from .vocab import Vocab, normalize, words

SCHEMA = 1
"""Version of the index format. The skill refuses to validate against any other."""

DEFAULT_SOURCE = "https://collinmurch.com/recipes/index.json"
NETWORK_HINT = "; in a chat app, network access may be off (see Setup in chat apps in SKILL.md)"

COURSES = ("breakfast", "main", "side", "sauce", "snack", "dessert", "drink")
LEFTOVERS = ("great", "good", "poor")
DIRS = {"recipe": "recipes", "drink": "drinks"}
PLANS = "plans"

SLUG = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
PLAN_ID = re.compile(r"(\d{4}-\d{2}-\d{2})(?:-([a-z0-9]+(?:-[a-z0-9]+)*))?")


def is_text(v) -> bool:
    return isinstance(v, str) and bool(v.strip())


def is_slug(v) -> bool:
    return isinstance(v, str) and bool(SLUG.fullmatch(v))


def is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0


def is_minutes(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v > 0


def is_date(v) -> bool:
    if not isinstance(v, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        return False
    try:
        date.fromisoformat(v)
        return True
    except ValueError:
        return False


@dataclass(frozen=True)
class Field:
    check: Callable[[object], bool]
    hint: str
    required: bool = False
    drinks_need: bool = True


FIELDS = {
    "title": Field(is_text, "text", required=True),
    "course": Field(lambda v: v in COURSES, ", ".join(COURSES), required=True),
    "cuisine": Field(is_slug, 'a lowercase word like "mexican"'),
    "servings": Field(is_number, "a number", required=True),
    "time_active": Field(is_minutes, "whole minutes"),
    "time_total": Field(is_minutes, "whole minutes", required=True, drinks_need=False),
    "leftovers": Field(lambda v: v in LEFTOVERS, ", ".join(LEFTOVERS)),
    "tags": Field(lambda v: isinstance(v, list) and all(map(is_slug, v)), "a list of lowercase words"),
    "rating": Field(lambda v: isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= 5, "1 to 5"),
    "source": Field(is_text, "a URL or text"),
    "description": Field(is_text, "text"),
    "pairs": Field(lambda v: isinstance(v, list) and all(map(is_slug, v)), "a list of recipe names"),
}

PLAN_FIELDS = ("title", "spent", "extras", "meals")
MEAL_FIELDS = ("recipe", "date", "servings", "cooked", "note")


@dataclass
class Problem:
    path: str
    message: str
    line: int | None = None
    level: str = "error"
    suggestions: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        where = f"{self.path}:{self.line}" if self.line else self.path
        return f"{where}: {self.level}: {self.message}"


def slugify(title: str) -> str:
    """The file name for a title: "Chicken, Pesto & Mozzarella" -> "chicken-pesto-and-mozzarella"."""
    return "-".join(words(title))


def compile_recipe(path: str, text: str, vocab: Vocab, draft: bool = False) -> tuple[dict, list[Problem]]:
    """Compiles a .cook file into an index record, resolving every ingredient
    through the vocab. A draft is named by its title; a filed recipe by its file."""
    problems: list[Problem] = []

    def report(message, line=None, level="error", **extra):
        problems.append(Problem(path, message, line, level, **extra))

    parsed = cooklang.parse(text)
    for error in parsed.errors:
        report(error.message, error.line)

    meta = parsed.metadata or {}
    if parsed.metadata is None and not parsed.errors:
        report("missing frontmatter (--- title, course, servings ... ---)")
    for key, value in meta.items():
        spec = FIELDS.get(key)
        if spec is None:
            report(f'unknown frontmatter key "{key}"; known keys are {", ".join(FIELDS)}')
        elif value is not None and not spec.check(value):
            report(f"{key} should be {spec.hint}, got {json.dumps(value)}")
    if parsed.metadata is not None:
        drink = meta.get("course") == "drink"
        for key, spec in FIELDS.items():
            if spec.required and (spec.drinks_need or not drink) and meta.get(key) is None:
                report(f"missing {key}")

    kind = "drink" if meta.get("course") == "drink" else "recipe"
    slug = slugify(meta.get("title") or "") if draft else Path(path).stem
    if not draft and not is_slug(slug):
        report(f'file name "{slug}" should be lowercase words joined by hyphens')

    proteins: set[str] = set()
    cookware: list[str] = []
    ingredients: list[dict] = []
    sections: list[dict] = []

    for section in parsed.sections:
        groups: dict[tuple, dict] = {}
        content = []
        for item in section.content:
            if isinstance(item, Note):
                content.append({"type": "note", "text": item.text})
                continue
            tokens = []
            for token in item.tokens:
                if isinstance(token, Text):
                    tokens.append({"type": "text", "value": token.value})
                elif isinstance(token, Cookware):
                    if token.name not in cookware:
                        cookware.append(token.name)
                    tokens.append({"type": "cookware", "text": token.name})
                elif isinstance(token, Timer):
                    tokens.append({"type": "timer", "text": token.name, "amount": str(token.amount)})
                else:
                    tokens.append(_ingredient(token, vocab, groups, proteins, report))
            content.append({"type": "step", "number": item.number, "text": step_text(tokens), "tokens": tokens})
        items = []
        for group in groups.values():
            amounts = [a for a in total(group.pop("amounts")) if a]
            entry = {
                **group,
                "amount": describe(amounts),
                "amounts": [a.to_json() for a in amounts],
                "note": "; ".join(group["note"]) or None,
            }
            items.append({**entry, "line": ingredient_line(entry)})
        if items:
            ingredients.append({"section": section.name, "items": items})
        sections.append({"name": section.name, "content": content})

    if not parsed.steps:
        report("recipe has no steps")

    record = {
        "slug": slug,
        "kind": kind,
        "path": path,
        **{k: meta[k] for k in FIELDS if meta.get(k) is not None},
        "proteins": sorted(proteins),
        "ingredients": ingredients,
        "cookware": cookware,
        "sections": sections,
    }
    return record, problems


def ingredient_line(item: dict, amount: str | None = None) -> str:
    """How an ingredient item reads in a list: "1.5 kg pork shoulder (cut into chunks)".
    Pass an amount to show a scaled one in place of the item's own."""
    amount = item["amount"] if amount is None else amount
    extras = [x for x in (item["note"], "optional" if item["optional"] else None) if x]
    line = " ".join(x for x in (amount, item["text"]) if x)
    return f"{line} ({', '.join(extras)})" if extras else line


def step_text(tokens: list[dict]) -> str:
    """A step's prose as it reads on the page, from its tokens."""
    shown = {"text": "value", "timer": "amount", "ingredient": "text", "cookware": "text"}
    return "".join(token[shown[token["type"]]] for token in tokens).strip()


def _ingredient(token: Ingredient, vocab: Vocab, groups: dict, proteins: set, report) -> dict:
    entry = vocab.lookup(token.name)
    if entry is None:
        suggestions = vocab.suggest(token.name)
        longer = f"{token.name} {token.next_word}" if token.next_word else None
        if longer and (vocab.lookup(longer) or not suggestions):
            hint = f'; names with spaces need braces, so if you meant "{longer}", write @{longer}{{}}'
        elif suggestions:
            hint = "; did you mean " + ", ".join(f'"{s}"' for s in suggestions) + "?"
        else:
            hint = ""
        written_as = "" if normalize(token.name) == token.name else f' (as "{normalize(token.name)}")'
        report(f'"{token.name}" is not in the vocab{written_as}{hint}', token.line, suggestions=suggestions)
    elif entry.protein and not token.optional:
        proteins.add(entry.protein)

    if token.amount and token.amount.unit and not canonical_unit(token.amount.unit):
        report(f'unknown unit "{token.amount.unit}" for {token.name}', token.line, "warning")

    name = entry.name if entry else None
    group = groups.setdefault(
        (name or normalize(token.name), token.optional),
        {
            "name": name,
            "text": token.name,
            "optional": token.optional,
            "note": [],
            "amounts": [],
        },
    )
    if token.amount:
        group["amounts"].append(token.amount)
    if token.note and token.note not in group["note"]:
        group["note"].append(token.note)
    return {
        "type": "ingredient",
        "text": token.name,
        "name": name,
        "amount": str(token.amount) if token.amount else "",
        "note": token.note,
        "optional": token.optional,
    }


def compile_plan(path: str, text: str) -> tuple[dict, list[Problem]]:
    """Compiles plans/<YYYY-MM-DD>[-name].md."""
    problems: list[Problem] = []

    def report(message):
        problems.append(Problem(path, message))

    plan_id = Path(path).stem
    match = PLAN_ID.fullmatch(plan_id)
    if not match or not is_date(match[1]):
        report("plan file should be named YYYY-MM-DD.md or YYYY-MM-DD-name.md")

    doc = yamlio.frontmatter(text)
    if doc.error:
        report(f"frontmatter: {doc.error}")
    elif doc.metadata is None:
        report("missing frontmatter")
    data = doc.metadata or {}

    for key in data:
        if key not in PLAN_FIELDS:
            report(f'unknown key "{key}"; known keys are {", ".join(PLAN_FIELDS)}')
    if "title" in data and not is_text(data["title"]):
        report("title should be text")
    if "spent" in data and not (is_number(data["spent"]) or data["spent"] == 0):
        report("spent should be a number")
    extras = data.get("extras", [])
    if not (isinstance(extras, list) and all(map(is_text, extras))):
        report("extras should be a list of names")
        extras = []
    meals = data.get("meals", [])
    if not isinstance(meals, list):
        report("meals should be a list")
        meals = []
    for n, meal in enumerate(meals, 1):
        if not isinstance(meal, dict):
            report(f"meal {n} should be a map")
            continue
        for key in meal:
            if key not in MEAL_FIELDS:
                report(f'meal {n}: unknown key "{key}"')
        if not is_slug(meal.get("recipe")):
            report(f"meal {n}: recipe should be a recipe name")
        for key in ("date", "cooked"):
            if key in meal and not is_date(meal[key]):
                report(f"meal {n}: {key} should be YYYY-MM-DD")
        if "servings" in meal and not is_number(meal["servings"]):
            report(f"meal {n}: servings should be a number")
        if "note" in meal and not is_text(meal["note"]):
            report(f"meal {n}: note should be text")

    plan = {
        "id": plan_id,
        "path": path,
        "start": match[1] if match else None,
        "name": match[2] if match else None,
        "title": data.get("title"),
        "spent": data.get("spent"),
        "extras": extras,
        "meals": [m for m in meals if isinstance(m, dict)],
        "notes": doc.body.strip(),
    }
    return plan, problems


def find_repo(start: Path) -> Path | None:
    """The repo root (the folder holding vocab.yaml and recipes/) at or above start."""
    for folder in [start.resolve(), *start.resolve().parents]:
        if (folder / "vocab.yaml").is_file() and (folder / DIRS["recipe"]).is_dir():
            return folder
    return None


def load_repo(root: Path) -> tuple[dict, Vocab, list[Problem]]:
    """Reads and checks everything in a checkout. Returns (index, vocab, problems)."""
    problems: list[Problem] = []
    try:
        vocab = Vocab.parse((root / "vocab.yaml").read_text())
        problems += [Problem("vocab.yaml", message) for message in vocab.check()]
    except (ValueError, TypeError, OSError) as e:
        line = getattr(e, "line", None)
        problems.append(Problem("vocab.yaml", str(e), line))
        vocab = Vocab()

    recipes = []
    for kind, folder in DIRS.items():
        for file in sorted((root / folder).glob("*.cook")):
            path = f"{folder}/{file.name}"
            record, found = compile_recipe(path, file.read_text(), vocab)
            problems += found
            if "course" in record and record["kind"] != kind:
                problems.append(Problem(path, f'course "{record["course"]}" belongs in {DIRS[record["kind"]]}/'))
            recipes.append(record)

    plans = []
    for file in sorted((root / PLANS).glob("*.md")):
        plan, found = compile_plan(f"{PLANS}/{file.name}", file.read_text())
        problems += found
        plans.append(plan)

    problems += _cross_check(recipes, plans)
    return _assemble(recipes, plans, vocab, _commit(root)), vocab, problems


def _cross_check(recipes: list[dict], plans: list[dict]) -> list[Problem]:
    problems = []
    by_slug: dict[str, dict] = {}
    for r in recipes:
        if r["slug"] in by_slug:
            problems.append(Problem(r["path"], f'"{r["slug"]}" is also {by_slug[r["slug"]]["path"]}'))
        by_slug[r["slug"]] = r
    for r in recipes:
        for other in r.get("pairs", []):
            if other == r["slug"]:
                problems.append(Problem(r["path"], "pairs lists the recipe itself"))
            elif other not in by_slug:
                problems.append(Problem(r["path"], f'pairs: no recipe named "{other}"'))
    for plan in plans:
        for meal in plan["meals"]:
            if is_slug(meal.get("recipe")) and meal["recipe"] not in by_slug:
                problems.append(Problem(plan["path"], f'no recipe named "{meal["recipe"]}"'))
    return problems


def _assemble(recipes: list[dict], plans: list[dict], vocab: Vocab, commit: str | None) -> dict:
    history: dict[str, list[str]] = {}
    for plan in plans:
        for meal in plan["meals"]:
            if is_date(meal.get("cooked")):
                history.setdefault(meal.get("recipe"), []).append(meal["cooked"])
    return {
        "schema": SCHEMA,
        "commit": commit,
        "recipes": [
            {
                **r,
                "last_cooked": max(history.get(r["slug"], []), default=None),
                "times_cooked": len(history.get(r["slug"], [])),
            }
            for r in sorted(recipes, key=lambda r: r["slug"])
        ],
        "plans": sorted(plans, key=lambda p: p["id"]),
        "vocab": vocab.to_json(),
        "units": units_json(),
    }


def _commit(root: Path) -> str | None:
    if sha := os.environ.get("GITHUB_SHA"):
        return sha
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True)
        return out.stdout.strip() or None
    except OSError:
        return None


class Collection:
    """Everything we've saved, read from a repo checkout or a published index."""

    def __init__(
        self,
        index: dict,
        vocab: Vocab,
        root: Path | None = None,
        origin: str = "",
        problems: list[Problem] | None = None,
    ):
        self.index = index
        self.vocab = vocab
        self.root = root
        self.origin = origin
        self.problems = problems or []
        self.by_slug = {r["slug"]: r for r in index["recipes"]}

    @property
    def mode(self) -> str:
        return "repo" if self.root else "index"

    @property
    def current(self) -> bool:
        return self.index.get("schema") == SCHEMA

    @property
    def recipes(self) -> list[dict]:
        return self.index["recipes"]

    @property
    def plans(self) -> list[dict]:
        return self.index["plans"]

    def recipe(self, slug: str) -> dict | None:
        return self.by_slug.get(slug)

    def plan(self, plan_id: str) -> dict | None:
        return next((p for p in self.plans if p["id"] == plan_id), None)

    def relative(self, path: Path | str) -> str:
        """A path relative to the repo when it's inside it, for messages."""
        path = Path(path).resolve()
        if self.root and path.is_relative_to(self.root):
            return path.relative_to(self.root).as_posix()
        return str(path)

    def filed(self, path: Path) -> str | None:
        """The repo path ("recipes/x.cook") if this file lives in the collection."""
        path = Path(path).resolve()
        if not self.root or not path.is_relative_to(self.root):
            return None
        relative = path.relative_to(self.root).as_posix()
        return relative if relative.split("/")[0] in (*DIRS.values(), PLANS) else None

    def check_drafts(self, drafts: list[tuple[str, str]]) -> list[tuple[dict, list[Problem]]]:
        """Checks drafts against the collection, together, so they can pair with
        each other. Takes (path, text) pairs; returns (record, problems) pairs."""
        compiled = [
            compile_plan(path, text) if path.endswith(".md") else compile_recipe(path, text, self.vocab, draft=True)
            for path, text in drafts
        ]
        known = set(self.by_slug)
        batch: dict[str, str] = {}
        for record, problems in compiled:
            slug = record.get("slug")
            if not slug:
                continue
            if slug in batch:
                problems.append(Problem(record["path"], f"same title as {batch[slug]}"))
            batch[slug] = record["path"]
            known.add(slug)
        for record, problems in compiled:
            if "meals" in record:
                named = [m["recipe"] for m in record["meals"] if is_slug(m.get("recipe"))]
                problems += [Problem(record["path"], f'no recipe named "{n}"') for n in named if n not in known]
            else:
                missing = [p for p in record.get("pairs", []) if p not in known]
                problems += [Problem(record["path"], f'pairs: no recipe named "{p}"') for p in missing]
        return compiled


def open_collection(source: str | None = None, cwd: Path | None = None) -> Collection:
    """Opens, in order: an explicit source (a repo folder, an index.json or its
    folder, or a URL), the repo around cwd, the repo holding this code, or the
    published index."""
    source = source if source is not None else os.environ.get("RECIPES_SOURCE") or None
    cwd = cwd or Path.cwd()
    if source and re.match(r"https?://", source):
        return _from_index(json.loads(download(source)), source)
    if source:
        path = (cwd / source).resolve()
        if (path / "vocab.yaml").is_file():
            return _from_repo(path)
        file = path / "index.json" if path.is_dir() else path
        return _from_index(json.loads(file.read_text()), str(file))
    root = find_repo(cwd) or find_repo(Path(__file__).parent)
    if root:
        return _from_repo(root)
    return _from_index(json.loads(download(DEFAULT_SOURCE)), DEFAULT_SOURCE)


def _from_repo(root: Path) -> Collection:
    index, vocab, problems = load_repo(root)
    return Collection(index, vocab, root=root, origin=str(root), problems=problems)


def _from_index(index: dict, origin: str) -> Collection:
    return Collection(index, Vocab.from_json(index.get("vocab", [])), origin=origin)


def download(url: str) -> str:
    """Fetches a URL, gzipped when the server allows. urllib honors the proxy
    settings sandboxes use."""
    request = urllib.request.Request(url, headers={"User-Agent": "recipes-skill", "Accept-Encoding": "gzip"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read()
            if response.headers.get("Content-Encoding") == "gzip":
                body = gzip.decompress(body)
            return body.decode()
    except urllib.error.HTTPError as e:
        hint = "" if e.code == 404 else NETWORK_HINT
        raise RuntimeError(f"could not download {url}: HTTP {e.code}{hint}") from None
    except OSError as e:
        raise RuntimeError(f"could not download {url}: {getattr(e, 'reason', e)}{NETWORK_HINT}") from None


def amounts_of(item: dict) -> list[Amount]:
    """The structured amounts of an index ingredient item."""
    return [Amount.from_json(a) for a in item.get("amounts", [])]
