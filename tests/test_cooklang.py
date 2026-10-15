from fractions import Fraction as F

from cookbook.cooklang import Cookware, Ingredient, Note, Step, Text, Timer, parse
from cookbook.units import Amount, Quantity


def ingredients(source: str) -> list[Ingredient]:
    return [t for t in parse(source).tokens if isinstance(t, Ingredient)]


def first(source: str, kind=Ingredient):
    return next(t for t in parse(source).tokens if isinstance(t, kind))


def test_frontmatter_is_read():
    assert parse("---\ntitle: Tacos\nservings: 4\n---\nCook.").metadata == {"title": "Tacos", "servings": 4}


def test_frontmatter_is_none_when_missing():
    assert parse("Cook.").metadata is None


def test_bad_frontmatter_is_reported_with_its_line():
    recipe = parse("---\ntitle: a\ntags: [x\n---\nCook.")
    assert recipe.metadata is None
    assert [e.line for e in recipe.errors] == [3]


def test_body_lines_are_numbered_after_the_frontmatter():
    assert parse("---\ntitle: a\n---\n\nCook @rice{}.").steps[0].line == 5


def test_a_single_word_needs_no_braces():
    assert first("Add @salt.") == Ingredient("salt", line=1)


def test_several_words_run_to_the_braces():
    assert first("Add @olive oil{}.").name == "olive oil"


def test_a_bare_name_stops_at_the_next_marker():
    assert [i.name for i in ingredients("Add @salt and @black pepper{}.")] == ["salt", "black pepper"]


def test_a_bare_name_remembers_the_next_word():
    assert first("Add @black pepper.").next_word == "pepper"


def test_quantity_is_read():
    assert first("Add @eggs{3}.").amount == Amount(Quantity(value=F(3)))


def test_quantity_and_unit_are_read():
    assert first("Add @flour{1 1/2%cups}.").amount == Amount(Quantity(value=F(3, 2)), "cups")


def test_empty_braces_mean_no_amount():
    assert first("Add @olive oil{}.").amount is None


def test_a_note_is_read():
    assert first("Add @onion{1}(diced).").note == "diced"


def test_the_optional_marker_is_read():
    assert first("Add @?cilantro{}.").optional


def test_hyphens_stay_in_bare_names():
    assert first("Add @pork-shoulder.").name == "pork-shoulder"


def test_an_unclosed_brace_is_reported():
    assert 'unclosed "{"' in parse("Add @salt{1%tsp.").errors[0].message


def test_a_lone_marker_is_text():
    assert parse("Email me @ home.").tokens == [Text("Email me @ home.")]


def test_cookware_is_read_with_and_without_braces():
    names = [t.name for t in parse("Use a #pot and a #dutch oven{}.").tokens if isinstance(t, Cookware)]
    assert names == ["pot", "dutch oven"]


def test_an_unnamed_timer_is_read():
    assert first("Wait ~{5%minutes}.", Timer) == Timer(None, Amount(Quantity(value=F(5)), "minutes"), 1)


def test_a_named_timer_is_read():
    assert first("Rest ~rest{10%minutes}.", Timer).name == "rest"


def test_a_tilde_without_braces_is_text():
    assert parse("About ~5 minutes.").tokens == [Text("About ~5 minutes.")]


def test_a_timer_needs_a_duration():
    assert "duration" in parse("Wait ~{}.").errors[0].message


def test_blank_lines_split_numbered_steps():
    assert [s.number for s in parse("One.\n\nTwo.").steps] == [1, 2]


def test_lines_within_a_step_are_joined():
    assert parse("One\ntwo.").tokens == [Text("One two.")]


def test_tokens_know_their_line():
    assert first("First line\nthen @salt.").line == 2


def test_notes_are_read():
    assert parse("> Keeps a week.").sections[0].content == [Note("Keeps a week.", 1)]


def test_sections_restart_numbering():
    sections = parse("Prep.\n\n== Sauce ==\n\nWhisk.\n\nPour.").sections
    numbers = [(s.name, [c.number for c in s.content if isinstance(c, Step)]) for s in sections]
    assert numbers == [(None, [1]), ("Sauce", [1, 2])]


def test_single_equals_sections_work():
    assert parse("= Dough\n\nMix.").sections[0].name == "Dough"


def test_line_comments_are_dropped():
    assert parse("Stir. -- gently").tokens == [Text("Stir.")]


def test_block_comments_are_dropped_without_moving_lines():
    assert parse("[- a\nb -]\n\nStir.").steps[0].line == 4


def test_old_style_metadata_is_rejected():
    assert "frontmatter" in parse(">> servings: 2").errors[0].message
