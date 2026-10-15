import pytest

from cookbook import schema_org
from cookbook.collection import compile_recipe
from cookbook.vocab import Vocab

VOCAB = Vocab.parse("produce:\n  lime: {}\n\nmeat:\n  pork-shoulder: {}\n\npantry:\n  salt: {}\n")

META = "title: Tacos\ncourse: main\nservings: 4\ntime_total: 150"


def record(meta: str = META, body: str = "Season @pork shoulder{1%kg}(cubed) with @salt.") -> dict:
    compiled, problems = compile_recipe("recipes/tacos.cook", f"---\n{meta}\n---\n\n{body}\n", VOCAB)
    assert [p.message for p in problems] == []
    return compiled


@pytest.fixture
def tacos():
    return schema_org.recipe(record())


def test_a_recipe_has_its_type_and_name(tacos):
    assert (tacos["@context"], tacos["@type"], tacos["name"]) == ("https://schema.org", "Recipe", "Tacos")


def test_the_category_and_cuisine_come_from_the_frontmatter():
    out = schema_org.recipe(record(META + "\ncuisine: mexican"))
    assert (out["recipeCategory"], out["recipeCuisine"]) == ("main", "mexican")


def test_tags_become_keywords():
    assert schema_org.recipe(record(META + "\ntags: [weekend, one-pot]"))["keywords"] == "weekend, one-pot"


def test_the_description_is_kept():
    assert schema_org.recipe(record(META + "\ndescription: Crisp pork."))["description"] == "Crisp pork."


def test_unset_fields_are_left_out(tacos):
    assert not {"description", "keywords", "recipeCuisine", "tool", "isBasedOn", "citation"} & tacos.keys()


def test_yield_counts_servings(tacos):
    assert tacos["recipeYield"] == "4 servings"
    assert schema_org.servings(1) == "1 serving"
    assert schema_org.servings(1.5) == "1.5 servings"


def test_total_time_is_an_iso_duration(tacos):
    assert tacos["totalTime"] == "PT2H30M"


def test_durations_drop_empty_parts():
    assert [schema_org.duration(m) for m in (45, 60, 150)] == ["PT45M", "PT1H", "PT2H30M"]


def test_ingredients_are_display_lines(tacos):
    assert tacos["recipeIngredient"] == ["1 kg pork shoulder (cubed)", "salt"]


def test_ingredients_from_every_section_are_listed_in_order():
    out = schema_org.recipe(record(body="Add @salt.\n\n== Garnish ==\n\nAdd @lime{1}."))
    assert out["recipeIngredient"] == ["salt", "1 lime"]


def test_cookware_becomes_tools():
    assert schema_org.recipe(record(body="Heat a #dutch oven{}. Add @salt."))["tool"] == ["dutch oven"]


def test_unnamed_steps_are_listed_directly(tacos):
    assert tacos["recipeInstructions"] == [
        {"@type": "HowToStep", "text": "Season pork shoulder with salt."},
    ]


def test_notes_become_tips():
    out = schema_org.recipe(record(body="Add @salt.\n\n> Keeps a week."))
    assert out["recipeInstructions"][1] == {"@type": "HowToTip", "text": "Keeps a week."}


def test_named_sections_wrap_their_steps():
    out = schema_org.recipe(record(body="Add @salt.\n\n== Garnish ==\n\nAdd @lime{1}.\n\nServe."))
    assert out["recipeInstructions"] == [
        {"@type": "HowToStep", "text": "Add salt."},
        {
            "@type": "HowToSection",
            "name": "Garnish",
            "itemListElement": [
                {"@type": "HowToStep", "text": "Add lime."},
                {"@type": "HowToStep", "text": "Serve."},
            ],
        },
    ]


def test_a_url_source_is_what_it_is_based_on():
    assert schema_org.recipe(record(META + "\nsource: https://example.com/t"))["isBasedOn"] == "https://example.com/t"


def test_a_text_source_is_a_citation():
    out = schema_org.recipe(record(META + "\nsource: Grandma"))
    assert (out["citation"], "isBasedOn" in out) == ("Grandma", False)


def test_drinks_without_a_time_have_no_total_time():
    out = schema_org.recipe(record("title: Sour\ncourse: drink\nservings: 1", "Shake @lime{1}."))
    assert ("totalTime" in out, out["recipeYield"]) == (False, "1 serving")


def test_a_graph_holds_recipes_under_one_context():
    out = schema_org.graph([record(), record("title: Salsa\ncourse: sauce\nservings: 2\ntime_total: 5")])
    assert out["@context"] == "https://schema.org"
    assert [(r["name"], "@context" in r) for r in out["@graph"]] == [("Tacos", False), ("Salsa", False)]
