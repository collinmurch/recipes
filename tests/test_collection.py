import urllib.error
import urllib.request
from email.message import Message

import pytest

from cookbook.collection import compile_plan, compile_recipe, download, ingredient_line, load_repo, slugify
from cookbook.vocab import Vocab

VOCAB = Vocab.parse("""produce:
  lime: {}
  scallion: {aka: [green onion]}
meat:
  pork-shoulder: {protein: pork}
pantry:
  salt: {}
""")

META = "title: Test\ncourse: main\nservings: 2\ntime_total: 30"


def recipe(meta: str = META, body: str = "Season @pork shoulder{1%kg} with @salt.") -> str:
    return f"---\n{meta}\n---\n\n{body}\n"


def compile(text: str, path: str = "recipes/test.cook"):
    return compile_recipe(path, text, VOCAB)


def messages(text: str) -> list[str]:
    return [p.message for p in compile(text)[1]]


def test_slugify_makes_a_file_name():
    assert slugify("Chicken, Pesto & Mozzarella Panini") == "chicken-pesto-and-mozzarella-panini"


def test_slugify_drops_apostrophes_and_accents():
    assert slugify("Grandma's Crème Brûlée") == "grandmas-creme-brulee"


def test_a_complete_recipe_has_no_problems():
    assert messages(recipe()) == []


def test_the_name_comes_from_the_file():
    assert compile(recipe())[0]["slug"] == "test"


def test_a_draft_is_named_by_its_title():
    record, _ = compile_recipe("/tmp/Draft 1.cook", recipe(), VOCAB, draft=True)
    assert record["slug"] == "test"


def test_ingredients_resolve_through_the_vocab():
    item = compile(recipe())[0]["ingredients"][0]["items"][0]
    assert (item["name"], item["text"], item["amount"]) == ("pork-shoulder", "pork shoulder", "1 kg")


def test_aliases_and_plurals_resolve():
    record, _ = compile(recipe(body="Top with @green onions{2} and @limes{2}."))
    assert [i["name"] for i in record["ingredients"][0]["items"]] == ["scallion", "lime"]


def test_proteins_come_from_the_vocab():
    assert compile(recipe())[0]["proteins"] == ["pork"]


def test_optional_ingredients_do_not_count_as_protein():
    assert compile(recipe(body="Add @?pork shoulder{1%kg}."))[0]["proteins"] == []


def test_repeat_mentions_in_a_section_are_merged():
    record, _ = compile(recipe(body="Add @lime{1}(juiced).\n\nGarnish with @lime{1/2}(in wedges)."))
    [item] = record["ingredients"][0]["items"]
    assert (item["amount"], item["note"]) == ("1 1/2", "juiced; in wedges")


def test_ingredients_are_grouped_by_section():
    record, _ = compile(recipe(body="Add @salt.\n\n== Garnish ==\n\nAdd @lime{1}."))
    assert [g["section"] for g in record["ingredients"]] == [None, "Garnish"]


def test_amounts_are_kept_structured():
    item = compile(recipe())[0]["ingredients"][0]["items"][0]
    assert item["amounts"] == [{"value": 1, "unit": "kg"}]


def test_steps_carry_tokens():
    step = compile(recipe(body="Rest ~{5%minutes}."))[0]["sections"][0]["content"][0]
    assert step["tokens"][1] == {"type": "timer", "text": None, "amount": "5 minutes"}


def test_only_known_metadata_is_kept():
    record, _ = compile(recipe(META + "\ntags: [quick]"))
    assert record["tags"] == ["quick"]
    assert "rating" not in record


def test_an_unknown_ingredient_comes_with_suggestions_and_a_line():
    _, problems = compile(recipe(body="Add @pork butt{1%kg}."))
    assert (problems[0].suggestions, problems[0].line) == (["pork-shoulder"], 8)


def test_a_multi_word_name_without_braces_is_explained():
    assert "write @pork shoulder{}" in messages(recipe(body="Add @pork shoulder."))[0]


def test_frontmatter_is_required():
    assert "missing frontmatter" in messages("Add @salt.")[0]


def test_title_course_servings_and_time_are_required():
    assert messages(recipe("cuisine: thai")) == [
        "missing title",
        "missing course",
        "missing servings",
        "missing time_total",
    ]


def test_drinks_need_no_time():
    assert messages(recipe("title: Sour\ncourse: drink\nservings: 1", "Shake.")) == []


def test_unknown_keys_are_rejected():
    assert 'unknown frontmatter key "chef"' in messages(recipe(META + "\nchef: me"))[0]


def test_bad_values_are_rejected():
    bad = "title: T\ncourse: lunch\nservings: two\ntime_total: 1.5\nrating: 9\nleftovers: meh"
    assert len(messages(recipe(bad))) == 5


def test_a_boolean_is_not_a_number():
    assert "servings should be" in messages(recipe("title: T\ncourse: main\nservings: true\ntime_total: 5"))[0]


def test_a_bad_file_name_is_rejected():
    assert "file name" in compile(recipe(), "recipes/My Recipe.cook")[1][0].message


def test_a_recipe_needs_a_step():
    assert "no steps" in messages(recipe(body="> Only a note."))[0]


def test_unknown_units_are_warnings():
    _, problems = compile(recipe(body="Add @salt{1%smidgen}."))
    assert [p.level for p in problems] == ["warning"]


def plan(body: str, path: str = "plans/2026-10-12.md"):
    return compile_plan(path, f"---\n{body}\n---\n\nNotes here.\n")


def test_a_week_plan_is_read():
    record, problems = plan("meals:\n  - recipe: tacos\n    cooked: 2026-10-13")
    assert problems == []
    assert (record["id"], record["start"], record["name"], record["notes"]) == (
        "2026-10-12",
        "2026-10-12",
        None,
        "Notes here.",
    )


def test_a_named_plan_is_read():
    record, _ = plan("meals: []", "plans/2026-10-18-dinner-party.md")
    assert (record["start"], record["name"]) == ("2026-10-18", "dinner-party")


def test_a_plan_needs_a_dated_name():
    assert "YYYY-MM-DD" in plan("meals: []", "plans/week-42.md")[1][0].message


def test_bad_meal_fields_are_rejected():
    _, problems = plan("meals:\n  - recipe: Tacos\n    cooked: yesterday\n    servings: 0\n    when: lunch")
    assert len(problems) == 4


def test_unknown_plan_keys_are_rejected():
    assert 'unknown key "budget"' in plan("budget: 100")[1][0].message


@pytest.fixture
def vocab_text():
    return VOCAB.stringify()


def test_load_repo_builds_cooking_history(make_repo, vocab_text):
    root = make_repo(
        {
            "recipes/tacos.cook": recipe("title: Tacos\ncourse: main\nservings: 2\ntime_total: 30"),
            "plans/2026-10-05.md": "---\nmeals:\n  - recipe: tacos\n    cooked: 2026-10-06\n---\n",
            "plans/2026-10-12.md": "---\nmeals:\n  - recipe: tacos\n    cooked: 2026-10-14\n  - recipe: tacos\n---\n",
        },
        vocab_text,
    )
    index, _, problems = load_repo(root)
    assert problems == []
    assert (index["recipes"][0]["last_cooked"], index["recipes"][0]["times_cooked"]) == ("2026-10-14", 2)


def test_load_repo_flags_a_drink_outside_drinks(make_repo, vocab_text):
    root = make_repo({"recipes/sour.cook": recipe("title: Sour\ncourse: drink\nservings: 1", "Shake.")}, vocab_text)
    assert "belongs in drinks/" in load_repo(root)[2][0].message


def test_load_repo_flags_a_name_used_twice(make_repo, vocab_text):
    root = make_repo(
        {
            "recipes/sour.cook": recipe("title: Sour\ncourse: side\nservings: 1\ntime_total: 5", "Shake."),
            "drinks/sour.cook": recipe("title: Sour\ncourse: drink\nservings: 1", "Shake."),
        },
        vocab_text,
    )
    assert any("is also" in p.message for p in load_repo(root)[2])


def test_load_repo_flags_pairs_that_name_nothing(make_repo, vocab_text):
    root = make_repo({"recipes/tacos.cook": recipe(META + "\npairs: [salsa]")}, vocab_text)
    assert 'no recipe named "salsa"' in load_repo(root)[2][0].message


def test_load_repo_flags_plans_that_name_nothing(make_repo, vocab_text):
    root = make_repo({"plans/2026-10-12.md": "---\nmeals:\n  - recipe: tacos\n---\n"}, vocab_text)
    assert 'no recipe named "tacos"' in load_repo(root)[2][0].message


def test_load_repo_flags_vocab_problems(make_repo):
    assert load_repo(make_repo({}, "produce:\n  Limes: {}\n"))[2][0].path == "vocab.yaml"


def test_load_repo_reports_unreadable_vocab(make_repo):
    assert load_repo(make_repo({}, "produce: [\n"))[2][0].path == "vocab.yaml"


def test_ingredient_items_carry_a_display_line():
    record, _ = compile(recipe(body="Add @lime{1}(juiced) and @?scallion{2}."))
    assert [i["line"] for i in record["ingredients"][0]["items"]] == ["1 lime (juiced)", "2 scallion (optional)"]


def test_an_ingredient_line_can_show_a_scaled_amount():
    item = compile(recipe())[0]["ingredients"][0]["items"][0]
    assert ingredient_line(item, "2 kg") == "2 kg pork shoulder"


def test_steps_carry_their_prose():
    step = compile(recipe(body="Rest @salt{1%tsp} in a #pot{} ~{5%minutes}."))[0]["sections"][0]["content"][0]
    assert step["text"] == "Rest salt in a pot 5 minutes."


def failing_urlopen(error):
    def urlopen(*_, **__):
        raise error

    return urlopen


def test_a_missing_index_reports_the_status(monkeypatch):
    error = urllib.error.HTTPError("https://x/index.json", 404, "Not Found", Message(), None)
    monkeypatch.setattr(urllib.request, "urlopen", failing_urlopen(error))
    with pytest.raises(RuntimeError, match=r"HTTP 404$"):
        download("https://x/index.json")


def test_a_blocked_request_points_to_setup(monkeypatch):
    error = urllib.error.HTTPError("https://x/index.json", 403, "Forbidden", Message(), None)
    monkeypatch.setattr(urllib.request, "urlopen", failing_urlopen(error))
    with pytest.raises(RuntimeError, match="HTTP 403; in a chat app, network access may be off"):
        download("https://x/index.json")


def test_an_unreachable_host_points_to_setup(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", failing_urlopen(urllib.error.URLError("no route to host")))
    with pytest.raises(RuntimeError, match="no route to host; in a chat app"):
        download("https://x/index.json")
