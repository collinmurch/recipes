"""YAML in and out, plus frontmatter.

Dates are kept as plain strings in both directions, so "2026-10-13" reads and
writes exactly as typed.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

import yaml


def _without_timestamps(base):
    return {
        first: [(tag, regexp) for tag, regexp in entries if tag != "tag:yaml.org,2002:timestamp"]
        for first, entries in base.yaml_implicit_resolvers.items()
    }


class Loader(yaml.SafeLoader):
    yaml_implicit_resolvers = _without_timestamps(yaml.SafeLoader)


class Dumper(yaml.SafeDumper):
    yaml_implicit_resolvers = _without_timestamps(yaml.SafeDumper)

    def increase_indent(self, flow=False, indentless=False):
        # Indent list items under their key: "meals:\n  - recipe: x".
        return super().increase_indent(flow, False)

    def represent_list(self, data):
        # Lists of plain values go on one line; lists of maps stay in block style.
        inline = self.default_flow_style or not any(isinstance(x, (dict, list)) for x in data)
        return self.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=inline)


Dumper.add_representer(list, Dumper.represent_list)


class YamlError(ValueError):
    def __init__(self, message: str, line: int | None = None):
        super().__init__(message)
        self.line = line


def load(text: str):
    """Parses YAML, raising YamlError with a 1-based line on failure."""
    try:
        return yaml.load(text, Loader=Loader)
    except yaml.MarkedYAMLError as e:
        mark = e.problem_mark or e.context_mark
        raise YamlError(e.problem or str(e), mark.line + 1 if mark else None) from None
    except yaml.YAMLError as e:
        raise YamlError(str(e)) from None


def dump(data) -> str:
    """Writes YAML in block style, with lists of plain values on one line."""
    return yaml.dump(data, Dumper=Dumper, sort_keys=False, allow_unicode=True, default_flow_style=False, width=math.inf)


def flow(data) -> str:
    """Writes a value on a single line: {aka: [green onion], protein: pork}."""
    return yaml.dump(
        data, Dumper=Dumper, sort_keys=False, allow_unicode=True, default_flow_style=True, width=math.inf
    ).strip()


FRONTMATTER = re.compile(r"\A---[ \t]*\n(?:(.*?)\n)?---[ \t]*(?:\n|\Z)", re.S)


@dataclass
class Document:
    """A text file split into its frontmatter and body."""

    metadata: dict | None
    body: str
    body_line: int
    error: YamlError | None = None

    @property
    def has_frontmatter(self) -> bool:
        return self.metadata is not None or self.error is not None


def frontmatter(text: str) -> Document:
    """Splits "---" delimited YAML off the top of a document."""
    text = text.replace("\r\n", "\n")
    match = FRONTMATTER.match(text)
    if not match:
        return Document(None, text, 1)
    body_line = match.group(0).count("\n") + 1
    body = text[match.end() :]
    try:
        data = load(match.group(1) or "")
    except YamlError as e:
        line = e.line + 1 if e.line else 1
        return Document(None, body, body_line, YamlError(str(e), line))
    if data is None:
        data = {}
    if not isinstance(data, dict):
        return Document(None, body, body_line, YamlError("frontmatter must be a map of keys", 2))
    return Document(data, body, body_line)


def write_frontmatter(data: dict, body: str = "") -> str:
    """Joins frontmatter and an optional body back into a document."""
    body = body.strip()
    return f"---\n{dump(data)}---\n" + (f"\n{body}\n" if body else "")
