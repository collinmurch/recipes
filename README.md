# Recipes

Our recipes, meal plans, and the tool that manages them. An AI agent writes and searches them in this repo, collinmurch.com publishes them, and Mela is where we cook from them.

```
agent ──push──▶ this repo ──CI──▶ collinmurch.com/recipes ──feed──▶ Mela
```

## Content

- **Recipes** are [Cooklang](https://cooklang.org) files, one dish per file. Ingredients are marked inside the steps, so lists and amounts are never typed twice. A meal is a main plus sides linked through `pairs`.
- **Plans** list a week's meals and when each was cooked. Grocery lists and "last cooked" are computed from them.
- **Vocab** (`vocab.yaml`) gives every ingredient one name, grouped by store section. That's what makes shared ingredients and grocery totals work. `pantry` and `bar` are staples, so they're left off shopping lists.

## Working on it

[`AGENTS.md`](AGENTS.md) (also `CLAUDE.md`) is the whole workflow, for people and agents alike, and [`docs/format.md`](docs/format.md) is the file format and house style. Everything runs through `scripts/recipes.py`.

To use it from a chat app or a session without the repo, install [`skill/recipes`](skill/recipes) as a skill. It only tells the agent to clone this repo and follow `AGENTS.md`, so it never needs re-uploading.

## Publishing

When a push to `main` passes its checks, CI builds a bundle and commits it to the site repo's `recipes-data/`. That push deploys [collinmurch.github.io](https://github.com/collinmurch/collinmurch.github.io). The bundle is:

- `index.json`: every recipe, plan, the vocab, and the units amounts use, described by [`docs/index.schema.json`](docs/index.schema.json)
- `jsonld/*.json`: schema.org Recipe JSON-LD per recipe

The site never parses Cooklang. New fields can appear at any time, and the schema number changes only when a field is removed or changes meaning.

The site serves `/recipes`, a page per recipe and plan, and `/recipes/feed.xml` for [Mela](https://mela.recipes). Mela subscribes to the feed, and each page embeds its JSON-LD so the share sheet can save it. Recipes import one way, and re-importing doesn't duplicate.

The only credential is `SITE_DEPLOY_KEY`, a write deploy key on the site repo, stored as a secret here.

## Development

```
uv sync
uv run ruff check && uv run ruff format --check && uv run ty check && uv run pytest
uv run scripts/recipes.py build   # writes the bundle to dist/
```

The conformance tests compare the parser with the [`cook` CLI](https://cooklang.org/cli/) when it's installed.
