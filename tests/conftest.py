from dataclasses import dataclass
from pathlib import Path

import pytest

from cookbook.cli import main

REPO = Path(__file__).resolve().parent.parent

VOCAB = """produce:
  cilantro: {}
  lime: {}

meat:
  pork-shoulder: {protein: pork}

pantry:
  salt: {}
"""

TACOS = """---
title: Tacos
course: main
servings: 4
time_total: 30
---

Season @pork shoulder{1%kg} with @salt. Serve with @limes{2} and @cilantro{1%bunch}.
"""

SALSA = """---
title: Salsa Verde
course: sauce
servings: 4
time_total: 10
pairs: [tacos]
---

Blend @cilantro{1/2%bunch} and @lime{1}.
"""


@dataclass
class Result:
    code: int
    out: str
    err: str


@pytest.fixture
def make_repo(tmp_path):
    """Creates a throwaway repo from {path: text}, with the test vocab by default."""

    def make(files: dict[str, str] | None = None, vocab: str = VOCAB) -> Path:
        root = tmp_path / "repo"
        (root / "recipes").mkdir(parents=True, exist_ok=True)
        (root / "vocab.yaml").write_text(vocab)
        for path, text in (files or {}).items():
            (root / path).parent.mkdir(parents=True, exist_ok=True)
            (root / path).write_text(text)
        return root

    return make


@pytest.fixture
def repo(make_repo):
    return make_repo({"recipes/tacos.cook": TACOS})


@pytest.fixture
def cli(monkeypatch, capsys):
    """Runs the CLI in a folder: cli(folder, "find", "--json")."""

    def run(cwd: Path, *args: str) -> Result:
        monkeypatch.chdir(cwd)
        try:
            code = main(list(args))
        except SystemExit as e:  # argparse exits 2 on bad arguments
            code = e.code if isinstance(e.code, int) else 1
        captured = capsys.readouterr()
        return Result(code, captured.out, captured.err)

    return run
