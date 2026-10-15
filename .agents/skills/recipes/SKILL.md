---
name: recipes
description: Plan meals and drinks from our saved recipe collection, search it, build combined grocery lists, write new recipes in Cooklang, and log what we cooked. Use when the user asks for dinner or drink ideas, a weekly or one-off meal plan, a shopping list, wants to save, port, or edit a recipe, or says they made something.
---

# Recipes

Our recipes are plain [Cooklang](https://cooklang.org) files in the `recipes` repo, published to collinmurch.com/recipes. Everything goes through one script, which needs Python 3.10+ and PyYAML:

```
python3 <this skill's folder>/scripts/recipes.py <command>
```

In the repo, use `uv run` in place of `python3`. Anywhere PyYAML is missing, `uv run --with pyyaml` does the same.

## Where it reads from

- **Inside a checkout of the recipes repo** (it has `vocab.yaml`), it reads the files directly and can write.
- **Anywhere else**, such as a claude.ai or ChatGPT chat, it downloads the published index from `https://collinmurch.com/recipes/index.json` and can only read and validate. If the download fails, the app's network access is probably off; walk the user through [Setup in chat apps](#setup-in-chat-apps).

`--source <repo folder | index.json | URL>` overrides this.

## Commands

| Command | Does |
|---|---|
| `find [words…]` | Search. Filters: `--course`, `--cuisine`, `--protein` (or `none`), `--tag`, `--uses <ingredient>` (repeatable), `--max-time <min>`, `--not-since <YYYY-MM-DD>`, `--kind recipe\|drink` |
| `show <name\|file>` | Show a recipe, or preview a draft, as it'll look on the site. `--servings <n>` scales it |
| `grocery <name[:servings]>…` | One shopping list for several recipes, grouped by store section. `--plan <id>` uses a plan's uncooked meals |
| `validate [files…]` | Check drafts, or the whole repo when no files are given. Exit 1 means errors |
| `vocab find <name>` / `vocab list [section]` | Look up ingredient names |
| `save <files…>` | Repo only. Check drafts together, name each from its title, and file it in `recipes/` or `drinks/` |
| `vocab add <name…> --section <s>` | Repo only. `--aka <alias>` (repeatable) and `--protein <p>` |
| `vocab alias <name> <alias…>` | Repo only |
| `plan <name[:servings]>…` | Repo only. Start or add to `plans/<monday>.md`. `--start <date>`, `--name <word>` for a one-off like a dinner party |
| `cooked <name>` | Repo only. Mark a planned meal cooked, or log an unplanned one. `--date`, `--plan` |
| `export <name\|file…>` / `export --all` | Print recipes as schema.org Recipe JSON-LD |

`find`, `show`, and `grocery` accept `--json`.

## Recipes as data

When someone wants a recipe in another app's format, start from data instead of reformatting prose by hand:

- `export` gives schema.org Recipe JSON-LD, the standard that recipe apps such as Mela and Paprika import.
- `show <name> --json` gives the full index record. [references/index.schema.json](references/index.schema.json) describes every field. `line` (an ingredient line) and `text` (a step) are ready to display, and `amounts` hold numbers for scaling.

Map from those fields; don't invent any.

## Planning meals

1. Look before suggesting: `find --course main --not-since <a month ago>` turns up neglected favorites, and `--uses cilantro` finds dishes that share a perishable.
2. Build the week around shared ingredients, so one bunch of herbs or one pack of chicken covers two dinners. Pay attention to `leftovers`: a "great" dish can cover lunches. Pair sides through each main's `pairs`.
3. Once the user agrees, run `grocery a b:6 c` and show the list. Staples (pantry and bar) come out as a separate "On hand" checklist.
4. In the repo, record it with `plan a b:6 c`, then commit and push.

## Writing or porting a recipe

Read [references/format.md](references/format.md) first. It covers the frontmatter, the Cooklang we use, and house style.

1. Write a draft to a scratch file. Use one dish per file; a meal is a main plus sides linked through `pairs`.
2. Run `validate draft.cook` and fix every error. For an unknown ingredient, make the call:
   - Same thing as a suggestion, or an existing entry ("coriander" is cilantro)? Add an alias: `vocab alias cilantro coriander`.
   - Genuinely new? Add it: `vocab add guajillo-chile --section pantry`. Give `--protein` for meat and fish.
   - Keep the prose natural ("green onions", "limes"). Aliases and plurals resolve on their own, so never reword a step just to match the vocab.
3. Run `show draft.cook` and share the preview.
4. In the repo, run `save draft.cook [other drafts…]`. Drafts saved together can pair with each other.

Without the repo (a claude.ai chat), validate against the published vocab. Then give the user the finished `.cook` files, plus any `vocab add` or `vocab alias` commands they need, so a session with the repo can save them in one go.

## Editing and logging

- To edit a recipe, change the file in place and run `validate`. If the title changed, `save recipes/<old>.cook` renames the file; then fix any `pairs` or plans that used the old name.
- When the user says they made something, run `cooked <name>` (add `--date` if it wasn't today). "Last cooked" comes from plans, so recipe files never change because of it.

## Finishing a session in the repo

Run `validate` with no files to check the whole collection. Make one commit for the session's work, with a plain message like `Add carnitas; plan week of 2026-10-12`, and push to `main`. CI re-runs the same checks and then rebuilds the site.

## Setup in chat apps

Chat apps block the internet by default, and the skill needs `collinmurch.com` to read the index.

- **Claude:** in Settings → Capabilities, turn on **Allow network egress**. Set **Domain allowlist** to **None**, and add `collinmurch.com` under **Additional allowed domains**. That's the most restrictive setting that still works.
- **ChatGPT:** in Settings → Data controls, turn on **Work network access**.
