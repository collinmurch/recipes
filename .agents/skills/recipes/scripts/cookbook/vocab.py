"""The ingredient dictionary: one name per ingredient, grouped by store section."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from . import yamlio

STAPLES = frozenset({"pantry", "bar"})
"""Sections we always have stocked, so they're left off shopping lists."""

ENTRY_KEYS = frozenset({"aka", "protein"})

_KEEP = {
    "bitters",
    "chips",
    "greens",
    "grits",
    "herbes",
    "molasses",
    "oats",
    "series",
    "species",
}
_IRREGULAR = {
    "feet": "foot",
    "geese": "goose",
    "halves": "half",
    "knives": "knife",
    "leaves": "leaf",
    "loaves": "loaf",
    "mice": "mouse",
    "teeth": "tooth",
}


def singularize(word: str) -> str:
    """Makes one English word singular: "limes" -> "lime", "leaves" -> "leaf"."""
    if word in _KEEP:
        return word
    if word in _IRREGULAR:
        return _IRREGULAR[word]
    if len(word) <= 3 or re.search(r"(ss|us|is|ics)$", word):
        return word
    if word.endswith("ies"):
        return word[:-3] + "y"
    if word.endswith("oes") or re.search(r"(ch|sh|x|z)es$", word):
        return word[:-2]
    if word.endswith("s"):
        return word[:-1]
    return word


def words(text: str) -> list[str]:
    """Lowercase ASCII words: "Grandma's Crème & Co." -> ["grandmas", "creme", "and", "co"]."""
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    text = re.sub("['\N{RIGHT SINGLE QUOTATION MARK}]", "", text.lower().replace("&", " and "))
    return re.findall(r"[a-z0-9]+", text)


def normalize(name: str) -> str:
    """The vocab form of a written name: "Green Onions" -> "green-onion"."""
    parts = words(name)
    if parts:
        parts[-1] = singularize(parts[-1])
    return "-".join(parts)


def humanize(name: str) -> str:
    """The vocab name as people read it: "pork-shoulder" -> "pork shoulder"."""
    return name.replace("-", " ")


@dataclass(frozen=True)
class Entry:
    name: str
    section: str
    aka: tuple[str, ...] = ()
    protein: str | None = None

    def to_yaml(self) -> dict:
        out = {}
        if self.aka:
            out["aka"] = list(self.aka)
        if self.protein:
            out["protein"] = self.protein
        return out


@dataclass
class Section:
    name: str
    items: dict[str, dict] = field(default_factory=dict)

    @property
    def staple(self) -> bool:
        return self.name in STAPLES


class Vocab:
    """Sections in store order, each holding entries by name."""

    def __init__(self, sections: list[Section] | None = None):
        self.sections = sections or []
        self._reindex()

    @classmethod
    def parse(cls, text: str) -> Vocab:
        data = yamlio.load(text) or {}
        if not isinstance(data, dict):
            raise ValueError("vocab must be a map of sections")
        return cls([Section(str(name), dict(items or {})) for name, items in data.items()])

    @classmethod
    def from_json(cls, sections: list[dict]) -> Vocab:
        return cls(
            [
                Section(
                    s["name"], {item["name"]: {k: v for k, v in item.items() if k != "name"} for item in s["items"]}
                )
                for s in sections
            ]
        )

    def to_json(self) -> list[dict]:
        return [
            {"name": s.name, "staple": s.staple, "items": [{"name": n, **(e or {})} for n, e in s.items.items()]}
            for s in self.sections
        ]

    def stringify(self) -> str:
        """The vocab in its one canonical layout: one entry per line, sorted."""
        blocks = []
        for section in self.sections:
            if not section.items:
                blocks.append(f"{section.name}: {{}}\n")
                continue
            lines = [f"  {name}: {yamlio.flow(entry or {})}" for name, entry in section.items.items()]
            blocks.append(f"{section.name}:\n" + "\n".join(lines) + "\n")
        return "\n".join(blocks)

    def _reindex(self) -> None:
        self.entries: dict[str, Entry] = {}
        self._index: dict[str, str] = {}
        self._conflicts: list[str] = []
        for section in self.sections:
            for name, data in section.items.items():
                data = data if isinstance(data, dict) else {}
                aka = data.get("aka")
                entry = Entry(
                    name,
                    section.name,
                    tuple(aka) if isinstance(aka, list) else (),
                    data.get("protein") if isinstance(data.get("protein"), str) else None,
                )
                if name in self.entries:
                    other = self.entries[name].section
                    self._conflicts.append(f'"{name}" is listed in both {other} and {section.name}')
                self.entries[name] = entry
                self._claim(name, name)
        for entry in list(self.entries.values()):
            for alias in entry.aka:
                self._claim(normalize(alias), entry.name, alias)

    def _claim(self, key: str, name: str, alias: str | None = None) -> None:
        owner = self._index.get(key)
        if owner and owner != name:
            self._conflicts.append(f'"{alias or key}" points to both "{owner}" and "{name}"')
            return
        self._index[key] = name

    def check(self) -> list[str]:
        """Problems with the vocab itself."""
        problems = list(self._conflicts)
        for section in self.sections:
            if not re.fullmatch(r"[a-z]+(-[a-z]+)*", section.name):
                problems.append(f'section "{section.name}" should be lowercase and hyphenated')
            names = list(section.items)
            if names != sorted(names):
                problems.append(f'section "{section.name}" is not in alphabetical order')
            for name, data in section.items.items():
                if normalize(name) != name:
                    problems.append(f'"{name}" should be written "{normalize(name)}"')
                if data is not None and not isinstance(data, dict):
                    problems.append(f'"{name}" should be a map like {{}} or {{aka: [...]}}')
                    continue
                for key in data or {}:
                    if key not in ENTRY_KEYS:
                        problems.append(f'"{name}" has unknown key "{key}"')
                aka = (data or {}).get("aka")
                if aka is not None and not (isinstance(aka, list) and all(isinstance(a, str) for a in aka)):
                    problems.append(f'"{name}": aka should be a list of names')
                protein = (data or {}).get("protein")
                if protein is not None and not isinstance(protein, str):
                    problems.append(f'"{name}": protein should be a word')
        return problems

    def lookup(self, written: str) -> Entry | None:
        """The entry a written name means, through aliases and plurals."""
        name = self._index.get(normalize(written))
        return self.entries[name] if name else None

    def suggest(self, written: str, limit: int = 3) -> list[str]:
        """The closest entries to an unknown name, best first."""
        target = normalize(written)
        if not target:
            return []
        target_words = set(target.split("-"))
        scores: dict[str, float] = {}
        for key, name in self._index.items():
            words = key.split("-")
            shared = sum(w in target_words for w in words) / max(len(words), len(target_words))
            shared += 0.5 if key in target or target in key else 0
            spelling = SequenceMatcher(None, key, target).ratio()
            score = max(shared if shared >= 0.5 else 0, spelling if spelling >= 0.75 else 0)
            if score:
                scores[name] = max(score, scores.get(name, 0))
        return sorted(scores, key=lambda n: (-scores[n], n))[:limit]

    def section(self, name: str) -> Section:
        for section in self.sections:
            if section.name == name:
                return section
        known = ", ".join(s.name for s in self.sections)
        raise ValueError(f'no section "{name}"; sections are: {known}')

    def add(self, written: str, section_name: str, aka: Iterable[str] = (), protein: str | None = None) -> str:
        """Adds an entry under its normalized name, keeping the section sorted."""
        name = normalize(written)
        if not name:
            raise ValueError(f'"{written}" is not a usable name')
        if existing := self.lookup(name):
            if existing.name == name:
                raise ValueError(f'"{name}" is already in {existing.section}')
            raise ValueError(f'"{name}" is already an alias of "{existing.name}"')
        aliases = sorted({a.strip().lower() for a in aka})
        for alias in aliases:
            if taken := self.lookup(alias):
                raise ValueError(f'"{alias}" already means "{taken.name}"')
        section = self.section(section_name)
        entry = Entry(name, section_name, tuple(aliases), protein)
        section.items = dict(sorted({**section.items, name: entry.to_yaml()}.items()))
        self._reindex()
        return name

    def alias(self, written: str, aliases: list[str]) -> str:
        """Adds other names for an existing entry."""
        entry = self.lookup(written)
        if not entry:
            raise ValueError(f'"{written}" is not in the vocab')
        for alias in aliases:
            if taken := self.lookup(alias):
                raise ValueError(f'"{alias}" already means "{taken.name}"')
        merged = sorted({*entry.aka, *(a.strip().lower() for a in aliases)})
        updated = Entry(entry.name, entry.section, tuple(merged), entry.protein)
        self.section(entry.section).items[entry.name] = updated.to_yaml()
        self._reindex()
        return entry.name
