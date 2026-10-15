import json

import pytest

from conftest import SALSA, TACOS, VOCAB


@pytest.fixture
def both(make_repo):
    return make_repo({"recipes/tacos.cook": TACOS, "recipes/salsa-verde.cook": SALSA})


def slugs(result) -> list[str]:
    return [r["slug"] for r in json.loads(result.out)]


def test_validate_passes_a_clean_repo(cli, repo):
    result = cli(repo, "validate")
    assert (result.code, result.out) == (0, "1 recipe, 0 plans: ok\n")


def test_validate_fails_with_file_and_line(cli, make_repo):
    root = make_repo({"recipes/tacos.cook": TACOS.replace("pork shoulder", "pork butt")})
    result = cli(root, "validate")
    assert result.code == 1
    assert 'recipes/tacos.cook:8: error: "pork butt" is not in the vocab' in result.out


def test_validate_checks_drafts_together(cli, repo):
    (repo / "a.cook").write_text(SALSA.replace("pairs: [tacos]", "pairs: [pickled-onions]"))
    (repo / "b.cook").write_text(SALSA.replace("Salsa Verde", "Pickled Onions").replace("[tacos]", "[salsa-verde]"))
    assert cli(repo, "validate", "a.cook", "b.cook").code == 0
    assert cli(repo, "validate", "a.cook").code == 1


def test_validate_flags_two_drafts_with_one_title(cli, repo):
    (repo / "a.cook").write_text(SALSA)
    (repo / "b.cook").write_text(SALSA)
    assert "same title" in cli(repo, "validate", "a.cook", "b.cook").out


def test_validate_reports_a_missing_file(cli, repo):
    assert "no such file" in cli(repo, "validate", "nope.cook").err


def test_show_renders_a_recipe(cli, repo):
    out = cli(repo, "show", "tacos").out
    assert out.startswith("# Tacos")
    assert "- 1 kg pork shoulder" in out
    assert "1. Season pork shoulder with salt" in out


def test_show_scales_servings(cli, repo):
    assert "- 2 kg pork shoulder" in cli(repo, "show", "tacos", "--servings", "8").out


def test_show_previews_a_draft(cli, repo):
    (repo / "draft.cook").write_text(SALSA)
    assert cli(repo, "show", "draft.cook").out.startswith("# Salsa Verde")


def test_show_suggests_close_names(cli, repo):
    assert 'did you mean "tacos"' in cli(repo, "show", "taco").err


def test_show_prints_json(cli, repo):
    assert json.loads(cli(repo, "show", "tacos", "--json").out)["slug"] == "tacos"


def test_find_filters_by_protein(cli, both):
    assert slugs(cli(both, "find", "--protein", "pork", "--json")) == ["tacos"]


def test_find_filters_by_no_protein(cli, both):
    assert slugs(cli(both, "find", "--protein", "none", "--json")) == ["salsa-verde"]


def test_find_filters_by_ingredient_through_plurals(cli, both):
    assert slugs(cli(both, "find", "--uses", "limes", "--json")) == ["salsa-verde", "tacos"]


def test_find_rejects_an_unknown_ingredient(cli, both):
    assert 'did you mean "pork-shoulder"' in cli(both, "find", "--uses", "pork butt").err


def test_find_searches_words(cli, both):
    assert slugs(cli(both, "find", "verde", "--json")) == ["salsa-verde"]


def test_find_filters_by_course(cli, both):
    assert slugs(cli(both, "find", "--course", "sauce", "--json")) == ["salsa-verde"]


def test_find_accepts_global_options_first(cli, both):
    assert slugs(cli(both, "--json", "find", "verde")) == ["salsa-verde"]


def test_find_prints_a_table(cli, both):
    assert "| tacos | Tacos | main |" in cli(both, "find").out


def test_grocery_combines_recipes_and_marks_shared_items(cli, both):
    out = cli(both, "grocery", "tacos", "salsa-verde").out
    assert "- [ ] cilantro — 1 1/2 bunches · tacos, salsa-verde" in out
    assert "- [ ] lime — 3" in out


def test_grocery_scales_by_servings(cli, repo):
    assert "pork shoulder — 2 kg" in cli(repo, "grocery", "tacos:8").out


def test_grocery_lists_staples_separately(cli, repo):
    assert "## On hand\n\nCheck these before you go:\n\n- pantry: salt" in cli(repo, "grocery", "tacos").out


def test_grocery_rejects_bad_servings(cli, repo):
    assert 'bad servings in "tacos:lots"' in cli(repo, "grocery", "tacos:lots").err


def test_grocery_needs_something(cli, repo):
    assert cli(repo, "grocery").code == 1


def test_save_files_a_draft_under_its_title(cli, repo):
    (repo / "draft.cook").write_text(SALSA)
    assert cli(repo, "save", "draft.cook").out == "saved recipes/salsa-verde.cook\n"
    assert (repo / "recipes/salsa-verde.cook").read_text() == SALSA


def test_save_files_drinks_in_drinks(cli, repo):
    (repo / "draft.cook").write_text("---\ntitle: Limeade\ncourse: drink\nservings: 1\n---\n\nSqueeze @lime{2}.\n")
    cli(repo, "save", "draft.cook")
    assert (repo / "drinks/limeade.cook").exists()


def test_save_refuses_a_draft_with_errors(cli, repo):
    (repo / "draft.cook").write_text(SALSA.replace("cilantro", "parsley"))
    assert cli(repo, "save", "draft.cook").code == 1
    assert not (repo / "recipes/salsa-verde.cook").exists()


def test_save_saves_nothing_if_any_draft_fails(cli, repo):
    (repo / "a.cook").write_text(SALSA)
    (repo / "b.cook").write_text(SALSA.replace("Salsa Verde", "Bad").replace("cilantro", "parsley"))
    assert cli(repo, "save", "a.cook", "b.cook").code == 1
    assert not (repo / "recipes/salsa-verde.cook").exists()


def test_save_needs_replace_to_overwrite(cli, repo):
    (repo / "draft.cook").write_text(TACOS.replace("{2}", "{3}"))
    assert "already exists" in cli(repo, "save", "draft.cook").out
    assert cli(repo, "save", "draft.cook", "--replace").code == 0
    assert "@limes{3}" in (repo / "recipes/tacos.cook").read_text()


def test_save_renames_a_filed_recipe_when_its_title_changes(cli, repo):
    (repo / "recipes/tacos.cook").write_text(TACOS.replace("Tacos", "Pork Tacos"))
    result = cli(repo, "save", "recipes/tacos.cook")
    assert "moved recipes/tacos.cook to recipes/pork-tacos.cook" in result.out
    assert not (repo / "recipes/tacos.cook").exists()


def test_save_leaves_a_filed_recipe_in_place(cli, repo):
    assert cli(repo, "save", "recipes/tacos.cook").out == "saved recipes/tacos.cook\n"


def test_vocab_add_keeps_the_file_canonical(cli, repo):
    assert cli(repo, "vocab", "add", "Guajillo Chiles", "--section", "pantry").code == 0
    assert "pantry:\n  guajillo-chile: {}\n  salt: {}\n" in (repo / "vocab.yaml").read_text()


def test_vocab_add_takes_aliases_and_protein(cli, repo):
    cli(repo, "vocab", "add", "chicken thigh", "--section", "meat", "--aka", "thighs", "--protein", "chicken")
    assert "chicken-thigh: {aka: [thighs], protein: chicken}" in (repo / "vocab.yaml").read_text()


def test_vocab_add_refuses_duplicates(cli, repo):
    result = cli(repo, "vocab", "add", "limes", "--section", "produce")
    assert (result.code, "already in produce" in result.err) == (1, True)


def test_vocab_alias_adds_a_name(cli, repo):
    cli(repo, "vocab", "alias", "cilantro", "coriander")
    assert cli(repo, "vocab", "find", "coriander").out == "coriander → cilantro (produce)\n"


def test_vocab_find_suggests_close_names(cli, repo):
    assert 'did you mean "pork-shoulder"' in cli(repo, "vocab", "find", "pork butt").out


def test_vocab_list_shows_a_section(cli, repo):
    assert cli(repo, "vocab", "list", "produce").out == "produce: cilantro, lime\n"


def test_plan_writes_a_week_and_its_groceries(cli, repo):
    result = cli(repo, "plan", "tacos:6", "--start", "2026-10-12")
    assert "wrote plans/2026-10-12.md" in result.out
    assert "pork shoulder — 1.5 kg" in result.out
    assert (repo / "plans/2026-10-12.md").read_text() == "---\nmeals:\n  - recipe: tacos\n    servings: 6\n---\n"


def test_plan_rejects_unknown_recipes(cli, repo):
    assert cli(repo, "plan", "nachos", "--start", "2026-10-12").code == 1
    assert not (repo / "plans").exists()


def test_plan_names_a_one_off(cli, repo):
    cli(repo, "plan", "tacos", "--start", "2026-10-18", "--name", "dinner-party")
    assert (repo / "plans/2026-10-18-dinner-party.md").exists()


def test_cooked_marks_a_planned_meal(cli, repo):
    cli(repo, "plan", "tacos", "--start", "2026-10-12")
    cli(repo, "cooked", "tacos", "--date", "2026-10-14")
    assert "cooked: 2026-10-14" in (repo / "plans/2026-10-12.md").read_text()
    assert "2026-10-14" in cli(repo, "find", "tacos").out


def test_cooked_logs_an_unplanned_meal_in_its_week(cli, repo):
    assert "plans/2026-10-12.md" in cli(repo, "cooked", "tacos", "--date", "2026-10-15").out


def test_cooked_keeps_plan_notes(cli, make_repo):
    root = make_repo(
        {
            "recipes/tacos.cook": TACOS,
            "plans/2026-10-12.md": "---\nmeals:\n  - recipe: tacos\n---\n\nBought too many limes.\n",
        }
    )
    cli(root, "cooked", "tacos", "--date", "2026-10-13")
    assert (root / "plans/2026-10-12.md").read_text().endswith("cooked: 2026-10-13\n---\n\nBought too many limes.\n")


def test_cooked_rejects_a_bad_date(cli, repo):
    assert cli(repo, "cooked", "tacos", "--date", "tuesday").code == 2


def test_grocery_from_a_plan_skips_cooked_meals(cli, both):
    cli(both, "plan", "tacos", "salsa-verde", "--start", "2026-10-12")
    cli(both, "cooked", "tacos", "--date", "2026-10-12")
    out = cli(both, "grocery", "--plan", "2026-10-12").out
    assert "pork shoulder" not in out
    assert "cilantro — 1/2 bunch" in out


def test_build_writes_the_index_and_sources(cli, repo):
    assert cli(repo, "build", "out").code == 0
    index = json.loads((repo / "out/index.json").read_text())
    assert (index["schema"], len(index["recipes"]), len(index["vocab"])) == (1, 1, 3)
    assert (repo / "out/sources/tacos.cook").read_text() == TACOS


def test_build_refuses_a_broken_collection(cli, make_repo):
    root = make_repo({"recipes/tacos.cook": TACOS.replace("limes", "lemons")})
    assert cli(root, "build", "out").code == 1
    assert not (root / "out/index.json").exists()


@pytest.fixture
def index(cli, repo):
    cli(repo, "build", "out")
    return repo / "out/index.json"


def test_index_mode_reads_a_built_index(cli, index, tmp_path):
    assert cli(tmp_path, "show", "tacos", "--source", str(index)).out.startswith("# Tacos")


def test_index_mode_accepts_the_bundle_folder(cli, index, tmp_path):
    assert "tacos" in cli(tmp_path, "--source", str(index.parent), "find").out


def test_index_mode_scales_like_the_repo(cli, index, repo, tmp_path):
    assert cli(tmp_path, "grocery", "tacos:6", "--source", str(index)).out == cli(repo, "grocery", "tacos:6").out


def test_index_mode_validates_drafts_against_the_published_vocab(cli, index, tmp_path):
    (tmp_path / "draft.cook").write_text(SALSA)
    assert cli(tmp_path, "validate", "draft.cook", "--source", str(index)).code == 0


def test_index_mode_refuses_writes(cli, index, tmp_path):
    assert "needs a checkout" in cli(tmp_path, "vocab", "add", "x", "--section", "produce", "--source", str(index)).err


def test_index_mode_refuses_a_newer_format(cli, index, tmp_path):
    data = json.loads(index.read_text())
    index.write_text(json.dumps({**data, "schema": 99}))
    (tmp_path / "draft.cook").write_text(SALSA)
    assert cli(tmp_path, "validate", "draft.cook", "--source", str(index)).code == 2


def test_vocab_fixture_is_canonical():
    from cookbook.vocab import Vocab

    assert Vocab.parse(VOCAB).stringify() == VOCAB


def test_export_prints_one_recipe_as_json_ld(cli, repo):
    out = json.loads(cli(repo, "export", "tacos").out)
    assert (out["@type"], out["name"], out["recipeYield"]) == ("Recipe", "Tacos", "4 servings")


def test_export_prints_several_recipes_as_a_graph(cli, both):
    out = json.loads(cli(both, "export", "tacos", "salsa-verde").out)
    assert [r["name"] for r in out["@graph"]] == ["Tacos", "Salsa Verde"]


def test_export_all_includes_everything(cli, both):
    out = json.loads(cli(both, "export", "--all").out)
    assert sorted(r["name"] for r in out["@graph"]) == ["Salsa Verde", "Tacos"]


def test_export_previews_a_draft(cli, repo):
    (repo / "draft.cook").write_text(SALSA)
    assert json.loads(cli(repo, "export", "draft.cook").out)["name"] == "Salsa Verde"


def test_export_needs_names_or_all(cli, repo):
    assert "needs recipe names or --all" in cli(repo, "export").err
    assert cli(repo, "export", "tacos", "--all").code == 1


def test_build_writes_json_ld_matching_export(cli, repo):
    cli(repo, "build", "out")
    built = json.loads((repo / "out/jsonld/tacos.json").read_text())
    assert built == json.loads(cli(repo, "export", "tacos").out)


def test_build_replaces_stale_files(cli, repo):
    cli(repo, "build", "out")
    (repo / "out/jsonld/gone.json").write_text("{}")
    (repo / "out/sources/gone.cook").write_text("")
    cli(repo, "build", "out")
    assert not (repo / "out/jsonld/gone.json").exists()
    assert not (repo / "out/sources/gone.cook").exists()


def test_show_json_has_ready_to_show_text(cli, repo):
    r = json.loads(cli(repo, "show", "tacos", "--json").out)
    assert r["ingredients"][0]["items"][0]["line"] == "1 kg pork shoulder"
    assert r["sections"][0]["content"][0]["text"] == "Season pork shoulder with salt. Serve with limes and cilantro."


def test_show_lines_match_the_index_unscaled(cli, repo):
    r = json.loads(cli(repo, "show", "tacos", "--json").out)
    shown = cli(repo, "show", "tacos").out
    for item in r["ingredients"][0]["items"]:
        assert f"- {item['line']}\n" in shown
