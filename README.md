# Recipes

Our recipes, meal plans, and the tool that manages them. An AI agent writes and searches them, collinmurch.com publishes them, and Mela is where we cook from them.

```
agent ──push──▶ this repo ──CI──▶ collinmurch.com/recipes ──feed──▶ Mela
  ▲                                         │
  └──────── searches the published index ───┘
```

## Content

- **Recipes** are [Cooklang](https://cooklang.org) files, one dish per file. Ingredients are marked inside the steps, so lists and amounts are never typed twice. A meal is a main plus sides linked through `pairs`.
- **Plans** list a week's meals and when each was cooked. Grocery lists and "last cooked" are computed from them.
- **Vocab** (`vocab.yaml`) gives every ingredient one name, grouped by store section. That's what makes shared ingredients and grocery totals work. `pantry` and `bar` are staples, so they're left off shopping lists.

## The skill

Everything goes through the `recipes` skill in `.agents/skills/recipes` (`.claude/skills` links to it). [`SKILL.md`](.agents/skills/recipes/SKILL.md) has the workflow and commands, and [`format.md`](.agents/skills/recipes/references/format.md) has the file format and house style.

Its script reads the repo when run inside a checkout. Anywhere else, it reads the published `index.json`, so chat apps can search, plan, and validate without the repo. Saving needs a checkout and a push.

## Publishing

When a push to `main` passes its checks, CI builds a bundle and commits it to the site repo's `recipes-data/`. That push deploys [collinmurch.github.io](https://github.com/collinmurch/collinmurch.github.io). The bundle is:

- `index.json`: every recipe, plan, and the vocab, described by [`index.schema.json`](.agents/skills/recipes/references/index.schema.json)
- `jsonld/*.json`: schema.org Recipe JSON-LD per recipe
- `sources/*.cook`: the raw files

The site never parses Cooklang. New fields can appear at any time, and the schema number changes only when a field is removed or changes meaning.

The site serves `/recipes`, a page per recipe and plan, `/recipes/index.json`, and `/recipes/feed.xml` plus `/recipes/all.melarecipes` for [Mela](https://mela.recipes). Mela subscribes to the feed. Recipes import one way, and re-importing doesn't duplicate.

The only credential is `SITE_DEPLOY_KEY`, a write deploy key on the site repo, stored as a secret here.

## Chat apps

Every CI run uploads the skill as the `recipes-skill` artifact. Upload its `recipes` folder as a skill, and let the app reach `collinmurch.com`:

- **Claude:** Settings → Capabilities → **Allow network egress**, with `collinmurch.com` as an additional allowed domain.
- **ChatGPT:** Settings → Data controls → **Work network access**.

Re-upload when the skill changes. Recipe changes don't need a re-upload.

## Development

```
uv sync
uv run ruff check && uv run ruff format --check && uv run ty check && uv run pytest
uv run .agents/skills/recipes/scripts/recipes.py validate
uv run .agents/skills/recipes/scripts/recipes.py build   # writes the bundle to dist/
```

The conformance tests compare the parser with the [`cook` CLI](https://cooklang.org/cli/) when it's installed.
