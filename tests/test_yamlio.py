import pytest

from cookbook.yamlio import YamlError, dump, flow, frontmatter, load, write_frontmatter


def test_load_keeps_dates_as_strings():
    assert load("cooked: 2026-10-13") == {"cooked": "2026-10-13"}


def test_load_reads_numbers_and_lists():
    assert load("servings: 4\ntags: [weekend, quick]") == {"servings": 4, "tags": ["weekend", "quick"]}


def test_load_reports_the_line_of_an_error():
    with pytest.raises(YamlError) as e:
        load("a: 1\nb: [1, 2")
    assert e.value.line == 2


def test_dump_keeps_dates_unquoted():
    assert dump({"cooked": "2026-10-13"}) == "cooked: 2026-10-13\n"


def test_dump_indents_lists_under_their_key():
    assert dump({"meals": [{"recipe": "a", "servings": 2}]}) == "meals:\n  - recipe: a\n    servings: 2\n"


def test_dump_writes_lists_of_plain_values_inline():
    assert dump({"extras": ["paper towels", "limes"]}) == "extras: [paper towels, limes]\n"


def test_dump_quotes_strings_that_would_read_as_numbers():
    assert load(dump({"a": "12"})) == {"a": "12"}


def test_dump_round_trips_a_plan():
    plan = {"title": "Soup week", "spent": 82.5, "meals": [{"recipe": "a", "cooked": "2026-10-13"}, {"recipe": "b"}]}
    assert load(dump(plan)) == plan


def test_flow_writes_one_line():
    assert flow({"aka": ["green onion"], "protein": "pork"}) == "{aka: [green onion], protein: pork}"


def test_flow_writes_an_empty_map():
    assert flow({}) == "{}"


def test_frontmatter_splits_metadata_and_body():
    doc = frontmatter("---\ntitle: Tacos\n---\n\nCook.\n")
    assert (doc.metadata, doc.body, doc.body_line) == ({"title": "Tacos"}, "\nCook.\n", 4)


def test_frontmatter_allows_an_empty_block():
    assert frontmatter("---\n---\nCook.").metadata == {}


def test_frontmatter_is_absent_without_dashes():
    doc = frontmatter("Cook.")
    assert (doc.metadata, doc.body, doc.body_line, doc.has_frontmatter) == (None, "Cook.", 1, False)


def test_frontmatter_needs_the_closing_dashes_on_their_own_line():
    assert frontmatter("---\ntitle: a---\nCook.").metadata is None


def test_frontmatter_reports_bad_yaml_with_the_file_line():
    doc = frontmatter("---\ntitle: a\ntags: [x\n---\nCook.")
    assert doc.metadata is None
    assert doc.error is not None
    assert doc.error.line == 3


def test_frontmatter_must_be_a_map():
    assert "map of keys" in str(frontmatter("---\n- a\n---\n").error)


def test_write_frontmatter_round_trips():
    text = write_frontmatter({"meals": [{"recipe": "a"}]}, "Notes.")
    assert text == "---\nmeals:\n  - recipe: a\n---\n\nNotes.\n"
    assert frontmatter(text).metadata == {"meals": [{"recipe": "a"}]}
