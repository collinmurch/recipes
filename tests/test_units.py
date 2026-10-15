from fractions import Fraction as F

from cookbook.units import Amount, Quantity, canonical_unit, format_number, total, unit_kind


def amount(text: str) -> Amount:
    parsed = Amount.parse(text)
    assert parsed is not None
    return parsed


def quantity(text: str) -> Quantity:
    parsed = Quantity.parse(text)
    assert parsed is not None
    return parsed


def value(a: Amount) -> F:
    assert a.quantity is not None and a.quantity.value is not None
    return a.quantity.value


def test_quantity_reads_whole_numbers():
    assert Quantity.parse("2") == Quantity(value=F(2))


def test_quantity_reads_decimals_exactly():
    assert quantity("1.5").value == F(3, 2)


def test_quantity_reads_fractions():
    assert quantity("1/2").value == F(1, 2)


def test_quantity_reads_mixed_numbers():
    assert quantity("1 1/2").value == F(3, 2)


def test_quantity_keeps_ranges_as_text():
    assert Quantity.parse("2-3") == Quantity(text="2-3")


def test_quantity_keeps_words_as_text():
    assert Quantity.parse("a pinch") == Quantity(text="a pinch")


def test_quantity_marks_equals_as_fixed():
    assert Quantity.parse("=2") == Quantity(value=F(2), fixed=True)


def test_quantity_is_none_when_empty():
    assert Quantity.parse("") is None
    assert Quantity.parse(None) is None


def test_quantity_keeps_a_zero_denominator_as_text():
    assert Quantity.parse("1/0") == Quantity(text="1/0")


def test_quantity_scales_exactly():
    assert quantity("1/3").scaled(F(3)).value == 1


def test_fixed_quantities_do_not_scale():
    assert quantity("=2").scaled(F(3)).value == 2


def test_text_quantities_do_not_scale():
    assert quantity("a pinch").scaled(F(2)).text == "a pinch"


def test_canonical_unit_maps_spellings():
    assert canonical_unit("tablespoons") == "tbsp"
    assert canonical_unit("Tbsp") == "tbsp"
    assert canonical_unit("cups") == "cup"
    assert canonical_unit("lbs") == "lb"


def test_canonical_unit_ignores_a_trailing_period():
    assert canonical_unit("tsp.") == "tsp"


def test_canonical_unit_knows_counted_units():
    assert canonical_unit("cloves") == "clove"
    assert canonical_unit("bunch") == "bunch"


def test_canonical_unit_is_none_when_unknown():
    assert canonical_unit("smidgen") is None


def test_unit_kind_groups_measured_units():
    assert [unit_kind(u) for u in ("g", "cup", "minute", "clove")] == ["mass", "volume", "time", "count"]


def test_format_number_writes_kitchen_fractions():
    assert [format_number(F(x)) for x in ("0.5", "1.5", "0.0625", "3")] == ["1/2", "1 1/2", "1/16", "3"]


def test_format_number_rounds_near_fractions():
    assert format_number(F("0.333")) == "1/3"


def test_format_number_uses_decimals_for_metric():
    assert format_number(F("1.5"), "kg") == "1.5"


def test_format_number_never_shows_a_small_amount_as_zero():
    assert format_number(F("0.01")) == "0.01"


def test_format_number_rounds_large_odd_amounts():
    assert format_number(F("12.41")) == "12"


def test_amount_parses_quantity_and_unit():
    assert amount("1 1/2%cups") == Amount(Quantity(value=F(3, 2)), "cups")


def test_amount_is_none_when_empty():
    assert Amount.parse("") is None
    assert Amount.parse(None) is None


def test_amount_pluralizes_word_units():
    assert [str(amount(x)) for x in ("2%cup", "1%cups", "6%cloves")] == ["2 cups", "1 cup", "6 cloves"]


def test_amount_uses_canonical_abbreviations():
    assert str(amount("2%tablespoons")) == "2 tbsp"


def test_amount_keeps_unknown_units_as_written():
    assert str(amount("2%smidgens")) == "2 smidgens"


def test_amount_shows_bare_counts_and_text():
    assert str(amount("12")) == "12"
    assert str(amount("2-3%minutes")) == "2-3 minutes"


def test_amount_json_round_trips_with_canonical_units():
    for text in ("1/3%cup", "2-3%minutes", "=1%tsp", "12"):
        a = amount(text)
        assert Amount.from_json(a.to_json()) == Amount(a.quantity, canonical_unit(a.unit) or a.unit)


def test_amount_json_uses_canonical_units():
    assert amount("2%tablespoons").to_json() == {"value": 2, "unit": "tbsp"}


def test_total_adds_the_same_unit():
    assert total([amount("1%cup"), amount("2%cups")]) == [Amount(Quantity(value=F(3)), "cup")]


def test_total_converts_within_a_kind_into_the_largest_unit():
    [result] = total([amount("1%cup"), amount("4%tbsp")])
    assert result.unit == "cup"
    assert abs(value(result) - F(5, 4)) < F(1, 100)


def test_total_keeps_kinds_apart():
    assert [a.unit for a in total([amount("1%lb"), amount("1%cup")])] == ["lb", "cup"]


def test_total_adds_bare_counts():
    assert total([amount("1"), amount("1/2")]) == [Amount(Quantity(value=F(3, 2)), None)]


def test_total_keeps_each_text_amount_once():
    assert len(total([amount("a pinch"), amount("a pinch")])) == 1


def test_total_marks_an_ingredient_with_no_amounts():
    assert total([]) == []
    assert total([Amount()]) == [Amount()]


def test_total_stays_fixed_only_when_every_part_is():
    assert total([amount("=1%g"), amount("=1%g")]) == [Amount(Quantity(F(2), fixed=True), "g")]
    assert total([amount("=1%g"), amount("1%g")]) == [Amount(Quantity(F(2)), "g")]
