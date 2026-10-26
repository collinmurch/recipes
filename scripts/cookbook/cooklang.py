"""A Cooklang parser that follows the reference `cook` CLI.

It knows nothing about the vocab: names are kept exactly as written.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import yamlio
from .units import Amount


@dataclass
class Text:
    value: str


@dataclass
class Ingredient:
    name: str
    amount: Amount | None = None
    note: str | None = None
    optional: bool = False
    line: int = 0
    next_word: str | None = None
    """The word after a name written without braces: "@black pepper" means "black"."""


@dataclass
class Cookware:
    name: str
    line: int = 0


@dataclass
class Timer:
    name: str | None
    amount: Amount
    line: int = 0


Token = Text | Ingredient | Cookware | Timer


@dataclass
class Step:
    number: int
    line: int
    tokens: list[Token]


@dataclass
class Note:
    text: str
    line: int


@dataclass
class Section:
    name: str | None
    content: list[Step | Note] = field(default_factory=list)


@dataclass
class ParseError:
    line: int
    message: str


@dataclass
class Recipe:
    metadata: dict | None
    sections: list[Section]
    errors: list[ParseError]

    @property
    def steps(self) -> list[Step]:
        return [c for s in self.sections for c in s.content if isinstance(c, Step)]

    @property
    def tokens(self) -> list[Token]:
        return [t for step in self.steps for t in step.tokens]


HEADER = re.compile(r"=+\s*(.*?)\s*=*")
WORD = re.compile(r"[\w-]+")


def parse(source: str) -> Recipe:
    doc = yamlio.frontmatter(source)
    errors = []
    if doc.error:
        errors.append(ParseError(doc.error.line or 1, f"frontmatter: {doc.error}"))

    sections = [Section(None)]
    block: list[tuple[int, str]] = []
    number = 0

    def flush():
        nonlocal number
        if not block:
            return
        if block[0][1].startswith(">"):
            text = " ".join(re.sub(r"^>\s?", "", t) for _, t in block).strip()
            sections[-1].content.append(Note(text, block[0][0]))
        else:
            number += 1
            sections[-1].content.append(Step(number, block[0][0], _tokenize(block, errors)))
        block.clear()

    for offset, raw in enumerate(_strip_comments(doc.body).split("\n")):
        line = doc.body_line + offset
        text = raw.strip()
        if not text:
            flush()
        elif header := HEADER.fullmatch(text):
            flush()
            if len(sections) == 1 and not sections[0].content:
                sections.pop()
            sections.append(Section(header[1] or None))
            number = 0
        elif text.startswith(">>"):
            errors.append(ParseError(line, 'old-style ">>" metadata is not supported; use frontmatter'))
        else:
            block.append((line, text))
    flush()

    sections = [s for s in sections if s.content or s.name]
    return Recipe(doc.metadata if not doc.error else None, sections, errors)


def _strip_comments(body: str) -> str:
    # Block comments are blanked rather than removed, so line numbers hold.
    body = re.sub(r"\[-.*?-\]", lambda m: re.sub(r"[^\n]", "", m[0]), body, flags=re.S)
    return re.sub(r"--.*$", "", body, flags=re.M)


def _tokenize(block: list[tuple[int, str]], errors: list[ParseError]) -> list[Token]:
    # A step's lines are joined with spaces; remember where each line starts.
    text, starts = "", []
    for line, part in block:
        if text:
            text += " "
        starts.append((len(text), line))
        text += part

    def line_at(offset: int) -> int:
        return max(line for start, line in starts if start <= offset)

    tokens: list[Token] = []
    plain, i = "", 0
    while i < len(text):
        result = _read(text, i, line_at(i)) if text[i] in "@#~" else None
        if result is None:
            plain += text[i]
            i += 1
        elif isinstance(result, str):
            errors.append(ParseError(line_at(i), result))
            plain += text[i]
            i += 1
        else:
            token, i = result
            if plain:
                tokens.append(Text(plain))
                plain = ""
            tokens.append(token)
    if plain:
        tokens.append(Text(plain))
    return tokens


def _read(text: str, start: int, line: int) -> tuple[Token, int] | str | None:
    """Reads one marked token at text[start]. Returns (token, end), an error, or None for plain text."""
    marker = text[start]
    kind = {"@": "ingredient", "#": "cookware", "~": "timer"}[marker]
    i = start + 1
    optional = marker == "@" and text[i : i + 1] == "?"
    i += optional

    # A name runs to the next "{" unless another marker comes first; otherwise it's one word.
    brace = text.find("{", i)
    span = text[i:brace] if brace >= 0 else None
    if span is not None and not re.search(r"[@#~{}]", span) and (span.strip() or marker == "~"):
        name, i = span.strip(), brace
    elif word := WORD.match(text, i):
        name, i = word[0], word.end()
    elif marker == "~":
        return None
    else:
        return f"{kind} is missing a name" if text[i : i + 1] == "{" else None

    raw = None
    if text[i : i + 1] == "{":
        close = text.find("}", i)
        if close < 0:
            return f'unclosed "{{" after {kind} "{name}"'
        raw, i = text[i + 1 : close], close + 1
    elif marker == "~":
        return None

    if marker == "#":
        return Cookware(name, line), i
    amount = Amount.parse(raw)
    if marker == "~":
        if not amount or not amount.quantity:
            return "timer is missing a duration"
        return Timer(name or None, amount, line), i

    note = None
    if text[i : i + 1] == "(":
        close = text.find(")", i)
        if close < 0:
            return f'unclosed "(" after ingredient "{name}"'
        note, i = text[i + 1 : close].strip() or None, close + 1
    next_word = None
    if raw is None and (after := re.match(r" ([\w-]+)", text[i:])):
        next_word = after[1]
    return Ingredient(name, amount, note, optional, line, next_word), i
