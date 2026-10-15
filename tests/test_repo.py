"""Checks of the real collection, so `pytest` alone is enough before pushing."""

from conftest import REPO
from cookbook.collection import load_repo
from cookbook.vocab import Vocab


def test_the_collection_has_no_errors():
    _, _, problems = load_repo(REPO)
    assert [str(p) for p in problems if p.level == "error"] == []


def test_the_vocab_is_in_canonical_form():
    text = (REPO / "vocab.yaml").read_text()
    assert Vocab.parse(text).stringify() == text
