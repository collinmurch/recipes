"""Quantities, units, and amounts: parsing, scaling, adding, and formatting.

Numbers are kept as exact fractions, so a third of a cup tripled is one cup.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from fractions import Fraction
from typing import NamedTuple


class Unit(NamedTuple):
    kind: str
    size: Fraction
    """Size in the kind's base unit: grams, milliliters, or seconds."""
    aliases: tuple[str, ...]
    plural: str | None = None


MEASURED = {
    "g": Unit("mass", Fraction(1), ("gram", "grams", "gr")),
    "kg": Unit("mass", Fraction(1000), ("kilogram", "kilograms", "kilo", "kilos")),
    "oz": Unit("mass", Fraction("28.3495"), ("ounce", "ounces")),
    "lb": Unit("mass", Fraction("453.592"), ("lbs", "pound", "pounds")),
    "ml": Unit("volume", Fraction(1), ("milliliter", "milliliters", "millilitre", "millilitres")),
    "l": Unit("volume", Fraction(1000), ("liter", "liters", "litre", "litres")),
    "tsp": Unit("volume", Fraction("4.92892"), ("teaspoon", "teaspoons", "tsps")),
    "tbsp": Unit("volume", Fraction("14.7868"), ("tablespoon", "tablespoons", "tbsps", "tbs", "tbl")),
    "fl oz": Unit("volume", Fraction("29.5735"), ("fl-oz", "floz", "fluid ounce", "fluid ounces")),
    "cup": Unit("volume", Fraction("236.588"), ("cups", "c"), "cups"),
    "pint": Unit("volume", Fraction("473.176"), ("pints", "pt"), "pints"),
    "quart": Unit("volume", Fraction("946.353"), ("quarts", "qt"), "quarts"),
    "second": Unit("time", Fraction(1), ("seconds", "s", "sec", "secs"), "seconds"),
    "minute": Unit("time", Fraction(60), ("minutes", "min", "mins", "m"), "minutes"),
    "hour": Unit("time", Fraction(3600), ("hours", "h", "hr", "hrs"), "hours"),
}

COUNTED = {
    "barspoon": "barspoons",
    "bottle": "bottles",
    "bunch": "bunches",
    "can": "cans",
    "clove": "cloves",
    "dash": "dashes",
    "drop": "drops",
    "handful": "handfuls",
    "head": "heads",
    "inch": "inches",
    "jar": "jars",
    "knob": "knobs",
    "leaf": "leaves",
    "package": "packages",
    "piece": "pieces",
    "pinch": "pinches",
    "slice": "slices",
    "splash": "splashes",
    "sprig": "sprigs",
    "stalk": "stalks",
    "stick": "sticks",
    "strip": "strips",
    "wedge": "wedges",
}

METRIC = {"g", "kg", "ml", "l"}

_SPELLINGS = {
    **{name: name for name in MEASURED},
    **{alias: name for name, unit in MEASURED.items() for alias in unit.aliases},
    **{name: name for name in COUNTED},
    **{plural: name for name, plural in COUNTED.items()},
}


def canonical_unit(unit: str | None) -> str | None:
    """The one name for a written unit ("Tablespoons" -> "tbsp"), or None if unknown."""
    if not unit:
        return None
    key = re.sub(r"\s+", " ", unit.strip().rstrip(".").lower())
    return _SPELLINGS.get(key)


def unit_kind(unit: str | None) -> str:
    """ "mass", "volume", "time", or "count"."""
    return MEASURED[unit].kind if unit in MEASURED else "count"


@dataclass(frozen=True)
class Quantity:
    """A number (exact) or free text like "2-3". Fixed quantities never scale."""

    value: Fraction | None = None
    text: str | None = None
    fixed: bool = False

    @classmethod
    def parse(cls, raw: str | None) -> Quantity | None:
        raw = (raw or "").strip()
        if not raw:
            return None
        fixed = raw.startswith("=")
        raw = raw.lstrip("=").strip()
        value = _number(raw)
        return cls(value=value, fixed=fixed) if value is not None else cls(text=raw, fixed=fixed)

    @property
    def numeric(self) -> bool:
        return self.value is not None

    def scaled(self, factor: Fraction) -> Quantity:
        if self.value is None or self.fixed or factor == 1:
            return self
        return replace(self, value=self.value * factor)

    def format(self, unit: str | None = None) -> str:
        if self.value is None:
            return self.text or ""
        return format_number(self.value, unit)


def _number(raw: str) -> Fraction | None:
    if re.fullmatch(r"\d+(\.\d+)?|\.\d+", raw):
        return Fraction(raw)
    if m := re.fullmatch(r"(\d+)\s*/\s*(\d+)", raw):
        return Fraction(int(m[1]), int(m[2])) if int(m[2]) else None
    if m := re.fullmatch(r"(\d+)\s+(\d+)\s*/\s*(\d+)", raw):
        return int(m[1]) + Fraction(int(m[2]), int(m[3])) if int(m[3]) else None
    return None


KITCHEN_DENOMINATORS = (2, 3, 4, 8, 16, 1)


def format_number(value: Fraction, unit: str | None = None) -> str:
    """ "1 1/2" for kitchen fractions, decimals for metric units or odd values."""
    if unit not in METRIC:
        for denominator in KITCHEN_DENOMINATORS:
            near = Fraction(round(value * denominator), denominator)
            if near and abs(value - near) < Fraction(1, 50):
                whole, rest = divmod(near, 1)
                if not rest:
                    return str(whole)
                fraction = f"{rest.numerator}/{rest.denominator}"
                return f"{whole} {fraction}" if whole else fraction
    if value >= 10:
        return str(round(value))
    return f"{float(value):.2f}".rstrip("0").rstrip(".")


@dataclass(frozen=True)
class Amount:
    """A quantity with an optional unit, as written: {1 1/2%cups}."""

    quantity: Quantity | None = None
    unit: str | None = None

    @classmethod
    def parse(cls, raw: str | None) -> Amount | None:
        if raw is None:
            return None
        quantity, _, unit = raw.partition("%")
        amount = cls(Quantity.parse(quantity), unit.strip() or None)
        return amount if amount else None

    def __bool__(self) -> bool:
        return self.quantity is not None or self.unit is not None

    def scaled(self, factor: Fraction) -> Amount:
        return replace(self, quantity=self.quantity.scaled(factor)) if self.quantity else self

    def __str__(self) -> str:
        canonical = canonical_unit(self.unit)
        if not self.quantity:
            return self.unit or ""
        number = self.quantity.format(canonical)
        if not self.unit:
            return number
        value = self.quantity.value
        many = value is None or value > 1
        return f"{number} {_display_unit(canonical, self.unit, many)}"

    def to_json(self) -> dict:
        out: dict = {}
        if self.quantity and self.quantity.value is not None:
            value = self.quantity.value
            out["value"] = int(value) if value.denominator == 1 else round(float(value), 6)
        elif self.quantity:
            out["text"] = self.quantity.text
        out["unit"] = canonical_unit(self.unit) or self.unit
        if self.quantity and self.quantity.fixed:
            out["fixed"] = True
        return out

    @classmethod
    def from_json(cls, data: dict) -> Amount:
        quantity = None
        if "value" in data:
            value = Fraction(str(data["value"])).limit_denominator(1000)
            quantity = Quantity(value=value, fixed=data.get("fixed", False))
        elif "text" in data:
            quantity = Quantity(text=data["text"], fixed=data.get("fixed", False))
        return cls(quantity, data.get("unit"))


def _display_unit(canonical: str | None, written: str, many: bool) -> str:
    if not canonical:
        return written
    plural = MEASURED[canonical].plural if canonical in MEASURED else COUNTED.get(canonical)
    return plural if plural and many else canonical


@dataclass
class _Sum:
    """A running total of one ingredient in one kind of unit."""

    base: Fraction = Fraction(0)
    units: set[str | None] = field(default_factory=set)
    fixed: bool = True

    def result(self) -> Amount:
        measured = [u for u in self.units if u in MEASURED]
        if not measured:
            return Amount(Quantity(value=self.base, fixed=self.fixed), next(iter(self.units)))
        unit = max(measured, key=lambda u: MEASURED[u].size)
        return Amount(Quantity(value=self.base / MEASURED[unit].size, fixed=self.fixed), unit)


def total(amounts: Iterable[Amount]) -> list[Amount]:
    """Adds amounts of one ingredient.

    Measured units of the same kind are converted and added in the largest unit
    used; counts add per unit; text amounts are kept once each. An ingredient
    used with no amount at all gives [Amount()].
    """
    sums: dict[str, _Sum] = {}
    others: dict[tuple, Amount] = {}
    bare = False
    for amount in amounts:
        unit = canonical_unit(amount.unit) or (amount.unit.strip().lower() if amount.unit else None)
        quantity = amount.quantity
        if quantity is None or quantity.value is None:
            if quantity is None and unit is None:
                bare = True
            else:
                text = quantity.text if quantity else None
                others.setdefault((text, unit), Amount(quantity, unit))
            continue
        measured = MEASURED.get(unit) if unit else None
        running = sums.setdefault(f"kind:{measured.kind}" if measured else f"unit:{unit}", _Sum())
        running.base += quantity.value * (measured.size if measured else 1)
        running.units.add(unit)
        running.fixed = running.fixed and quantity.fixed

    out = [running.result() for running in sums.values()]
    out.extend(others.values())
    if not out and bare:
        out.append(Amount())
    return out


def describe(amounts: Iterable[Amount]) -> str:
    """Formats several amounts of one thing: "1 lb + 2 cups"."""
    return " + ".join(str(a) for a in amounts if a)
