# Recipes

This repo is our recipe collection: [Cooklang](https://cooklang.org) recipes, meal plans, and the ingredient vocab. CI publishes it to collinmurch.com/recipes, and Mela picks it up from there.

Everything goes through one script, which needs Python 3.10+ and PyYAML (`python3 -m pip install pyyaml` if it's missing):

```
python3 scripts/recipes.py <command>
```

Use it for anything it has a command for instead of editing `vocab.yaml` or plans by hand. Read [docs/format.md](docs/format.md) before writing or editing a recipe.

## Commands

| Command | Does |
|---|---|
| `find [words…]` | Search. Filters: `--course`, `--cuisine`, `--protein` (or `none`), `--tag`, `--uses <ingredient>` (repeatable), `--max-time <min>`, `--not-since <YYYY-MM-DD>`, `--kind recipe\|drink`. `--sort title\|cooked\|time`; shows 20 unless `--limit <n>` (0 for all) |
| `show <name\|file>…` | Show recipes, or preview drafts, as they'll look on the site. Drafts shown together can pair with each other. `--servings <n>` scales them |
| `grocery <name[:servings]>…` | One shopping list for several recipes, grouped by store section. `--plan <id>` uses a plan's uncooked meals |
| `validate [files…]` | Check drafts, or the whole repo when no files are given. Exit 1 means errors |
| `save <files…>` | Check drafts together, name each from its title, and file it in `recipes/` or `drinks/` |
| `vocab find <name>` / `vocab list [section]` | Look up ingredient names |
| `vocab add <name…> --section <s>` | Add ingredients. `--aka <alias>` (repeatable) and `--protein <p>` |
| `vocab alias <name> <alias…>` | Add other names for an entry |
| `plan <name[:servings]>…` | Start or add to `plans/<monday>.md`. `--start <date>`, `--name <word>` for a one-off like a dinner party |
| `cooked <name>` | Mark a planned meal cooked, or log an unplanned one. `--date`, `--plan` |
| `export <name\|file…>` / `export --all` | Print recipes as schema.org Recipe JSON-LD |
| `build [dir]` | Check everything and write the site bundle (`index.json` and `jsonld/`). CI runs it |

`find`, `show`, and `grocery` accept `--json`.

Query the collection through the script rather than opening files in bulk; it prints only answers. Narrow `find` with filters rather than raising `--limit`. Read recipes with `show`; `show --json` is about ten times longer and only worth it for converting a recipe.

## Planning meals

1. Look before suggesting: `find --course main --sort cooked` puts neglected favorites first, and `--uses cilantro` finds dishes that share a perishable.
2. Build the week around shared ingredients, so one bunch of herbs or one pack of chicken covers two dinners. Pay attention to `leftovers`: a "great" dish can cover lunches. Pair sides through each main's `pairs`.
3. Once the user agrees, run `grocery a b:6 c` and show the list. Staples (pantry and bar) come out as a separate "On hand" checklist.
4. Record it with `plan a b:6 c`.

## Writing or porting a recipe

1. Write a draft to a scratch file. Use one dish per file; a meal is a main plus sides linked through `pairs`.
2. Run `validate draft.cook [other drafts…]` and fix every error. Don't look names up one at a time first; validate lists the unknown ones with a `vocab add` command to finish. For each, make the call:
   - Same thing as a suggestion, or an existing entry ("coriander" is cilantro)? Add an alias: `vocab alias cilantro coriander`.
   - Genuinely new? Add it: `vocab add guajillo-chile --section pantry`. Give `--protein` for meat and fish.
   - Keep the prose natural ("green onions", "limes"). Aliases and plurals resolve on their own, so never reword a step just to match the vocab.
3. Run `show draft.cook [other drafts…]` and share the preview.
4. Run `save draft.cook [other drafts…]`. Drafts saved together can pair with each other.

## Editing and logging

- To edit a recipe, change the file in place and run `validate`. If the title changed, `save recipes/<old>.cook` renames the file; then fix any `pairs` or plans that used the old name (`validate` finds them).
- When the user says they made something, run `cooked <name>` (add `--date` if it wasn't today). "Last cooked" comes from plans, so recipe files never change because of it.

## Recipes for other apps

Start from data instead of reformatting prose by hand:

- `export` gives schema.org Recipe JSON-LD, the standard that recipe apps such as Mela and Paprika import.
- `show <name> --json` gives the full index record, described field by field in [docs/index.schema.json](docs/index.schema.json). `line` (an ingredient line) and `text` (a step) are ready to display, and `amounts` hold numbers for scaling.

Map from those fields; don't invent any.

## Finishing a session

Run `validate` with no files to check the whole collection. Make one commit for the session's work, with a plain message like `Add carnitas; plan week of 2026-10-12`, and push to `main`. CI re-runs the checks and publishes the site.

## Changing the tool

Run what CI runs: `uv run ruff check`, `uv run ruff format --check`, `uv run ty check`, and `uv run pytest`.

The site renders only the bundle `build` writes, as described in `docs/index.schema.json`, and never parses Cooklang. Adding a field is always safe. Removing one or changing what it means needs a new `SCHEMA` in `scripts/cookbook/collection.py`, and the site has to learn that schema first. Don't edit the site repo from here.
