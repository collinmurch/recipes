import pytest

from cookbook.vocab import Entry, Section, Vocab, humanize, normalize, singularize

SAMPLE = """produce:
  cilantro: {aka: [coriander]}
  scallion: {aka: [green onion, spring onion]}

meat:
  pork-shoulder: {protein: pork}

aisles:
  chipotle-in-adobo: {}

pantry:
  cumin: {}
"""


@pytest.fixture
def vocab():
    return Vocab.parse(SAMPLE)


def test_singularize_drops_a_plain_s():
    assert singularize("limes") == "lime"


def test_singularize_handles_es_endings():
    assert [singularize(w) for w in ("berries", "tomatoes", "radishes")] == ["berry", "tomato", "radish"]


def test_singularize_handles_irregular_words():
    assert singularize("leaves") == "leaf"


def test_singularize_leaves_words_that_only_look_plural():
    assert [singularize(w) for w in ("asparagus", "molasses", "bitters", "peas")] == [
        "asparagus",
        "molasses",
        "bitters",
        "pea",
    ]


def test_normalize_lowercases_hyphenates_and_singularizes():
    assert normalize("Green Onions") == "green-onion"


def test_normalize_only_singularizes_the_last_word():
    assert normalize("brussels sprouts") == "brussels-sprout"


def test_normalize_strips_accents_and_punctuation():
    assert normalize("Jalapeños") == "jalapeno"
    assert normalize("Chef's Knife!") == "chefs-knife"
    assert normalize("salt & pepper") == "salt-and-pepper"
    assert normalize("Chef\u2019s Knives") == "chefs-knife"


def test_normalize_treats_hyphens_and_spaces_alike():
    assert normalize("extra-virgin olive oil") == normalize("extra virgin olive oil")


def test_normalize_is_stable():
    assert normalize(normalize("Bay Leaves")) == "bay-leaf"


def test_humanize_turns_hyphens_into_spaces():
    assert humanize("pork-shoulder") == "pork shoulder"


def test_lookup_finds_a_name(vocab):
    assert vocab.lookup("cumin") == Entry("cumin", "pantry")


def test_lookup_finds_a_name_written_differently(vocab):
    assert vocab.lookup("Pork Shoulder").name == "pork-shoulder"


def test_lookup_finds_an_alias_through_plurals(vocab):
    assert vocab.lookup("green onions").name == "scallion"


def test_lookup_returns_none_for_unknown_names(vocab):
    assert vocab.lookup("guajillo") is None


def test_suggest_finds_names_sharing_a_word(vocab):
    assert vocab.suggest("pork butt") == ["pork-shoulder"]


def test_suggest_finds_names_containing_the_word(vocab):
    assert vocab.suggest("chipotle") == ["chipotle-in-adobo"]


def test_suggest_finds_close_spellings(vocab):
    assert vocab.suggest("cilantr") == ["cilantro"]


def test_suggest_nothing_for_unrelated_names(vocab):
    assert vocab.suggest("vanilla") == []


def test_add_normalizes_and_sorts(vocab):
    assert vocab.add("Avocados", "produce") == "avocado"
    assert list(vocab.sections[0].items) == ["avocado", "cilantro", "scallion"]


def test_add_stores_aliases_and_protein(vocab):
    vocab.add("chicken thigh", "meat", aka=["Thighs"], protein="chicken")
    assert vocab.lookup("thighs") == Entry("chicken-thigh", "meat", ("thighs",), "chicken")


def test_add_refuses_an_existing_name(vocab):
    with pytest.raises(ValueError, match="already in pantry"):
        vocab.add("cumin", "pantry")


def test_add_refuses_an_existing_alias(vocab):
    with pytest.raises(ValueError, match='alias of "scallion"'):
        vocab.add("spring onions", "produce")


def test_add_refuses_an_alias_taken_elsewhere(vocab):
    with pytest.raises(ValueError, match='already means "cilantro"'):
        vocab.add("parsley", "produce", aka=["coriander"])


def test_add_refuses_an_unknown_section(vocab):
    with pytest.raises(ValueError, match='no section "liquor-store"'):
        vocab.add("rye", "liquor-store")


def test_alias_adds_names_in_order(vocab):
    vocab.alias("cilantro", ["Chinese parsley"])
    assert vocab.sections[0].items["cilantro"] == {"aka": ["chinese parsley", "coriander"]}
    assert vocab.lookup("chinese parsley").name == "cilantro"


def test_alias_refuses_a_name_another_entry_owns(vocab):
    with pytest.raises(ValueError, match='already means "scallion"'):
        vocab.alias("cilantro", ["green onion"])


def test_alias_refuses_an_unknown_entry(vocab):
    with pytest.raises(ValueError, match="not in the vocab"):
        vocab.alias("guajillo", ["dried chile"])


def test_check_passes_a_clean_vocab(vocab):
    assert vocab.check() == []


def test_check_flags_unnormalized_names():
    assert 'should be written "lime"' in Vocab.parse("produce:\n  Limes: {}").check()[0]


def test_check_flags_a_name_listed_twice():
    assert "both produce and pantry" in " ".join(Vocab.parse("produce:\n  lime: {}\npantry:\n  lime: {}").check())


def test_check_flags_a_shared_alias():
    assert '"x" points to both' in " ".join(Vocab.parse("produce:\n  a: {aka: [x]}\n  b: {aka: [x]}").check())


def test_check_flags_unsorted_sections():
    assert "alphabetical" in " ".join(Vocab.parse("produce:\n  lime: {}\n  apple: {}").check())


def test_check_flags_unknown_keys():
    assert 'unknown key "color"' in " ".join(Vocab.parse("produce:\n  lime: {color: green}").check())


def test_check_flags_entries_that_are_not_maps():
    assert "should be a map" in " ".join(Vocab.parse("produce:\n  lime: green").check())


def test_stringify_round_trips(vocab):
    assert Vocab.parse(vocab.stringify()).to_json() == vocab.to_json()


def test_stringify_is_canonical():
    assert Vocab.parse(SAMPLE).stringify() == SAMPLE


def test_stringify_writes_empty_sections_inline():
    assert Vocab([Section("frozen")]).stringify() == "frozen: {}\n"


def test_json_marks_staples(vocab):
    assert [(s["name"], s["staple"]) for s in vocab.to_json()] == [
        ("produce", False),
        ("meat", False),
        ("aisles", False),
        ("pantry", True),
    ]


def test_json_round_trips(vocab):
    assert Vocab.from_json(vocab.to_json()).to_json() == vocab.to_json()
