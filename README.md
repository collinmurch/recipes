# Recipes

Plan meals with Claude, keep the recipes as plain files we own, and cook from a nice app on the phone.

You work out a dinner or drink with Claude. Claude saves it as a `.cook` file in this repo. The repo rebuilds the recipe pages on collinmurch.com, and the site's RSS feed sends new recipes to Mela on iOS. Claude can also search everything we've saved, so a week of meals can share ingredients and come from one grocery trip.

It's all free apart from the domain, and Claude only has access to this one repo.

```
Claude ──push──▶ this repo ──check passes──▶ collinmurch.com/recipes ──RSS──▶ Mela
   ▲                                                   │
   └──────────── searches the published index ─────────┘
```

There are four parts: this repo, the skill, the website, and Mela.

## 1. This repo

The source of truth. It holds content, plus the one tool that reads it.

```
recipes/*.cook            food, one dish per file
drinks/*.cook             drinks
plans/*.md                a week per file (2026-10-12.md), or a one-off (2026-12-24-christmas-eve.md)
vocab.yaml                every ingredient name, grouped by store section
.agents/skills/recipes/   the skill: SKILL.md, the format reference, and the Python tool
.claude/skills            a symlink to .agents/skills, so Claude Code and Codex share one copy
tests/                    pytest tests for the tool, plus a check of the whole collection
pyproject.toml, uv.lock   the dev environment (PyYAML, pytest, ruff, ty), managed with uv
```

**Recipes** are written in [Cooklang](https://cooklang.org). Ingredients are marked inside the steps (`@cilantro{1%bunch}`), so the ingredient list, amounts, and equipment come from the steps instead of being typed twice. The frontmatter holds only what the steps can't tell you: title, course, cuisine, servings, times, how well it keeps, tags, the dishes it pairs with, rating, and source. A meal is a main plus its sides, linked through `pairs`, so a good side can go with more than one main. The files are standard Cooklang, and the parser is checked against the official `cook` CLI.

**Plans** list the meals, when each was cooked, notes, and what we spent. The grocery list is worked out from the meals instead of being stored, so it can't drift. "Last cooked" comes from the plans, so a recipe file never changes just because we made it.

**Vocab** is the dictionary of ingredient names. Each name appears once, under its store section, and the sections are in the order we walk the store. `pantry` and `bar` hold things we always have, so they're left off shopping lists.

```yaml
produce:
  cilantro: {aka: [coriander]}
  scallion: {aka: [green onion, spring onion]}
meat:
  pork-shoulder: {aka: [pork butt], protein: pork}
pantry:
  cumin: {}
bar:
  rye: {aka: [rye whiskey]}
```

### Adding ingredients

One name per ingredient is what makes shared ingredients and shopping-list totals work. Recipes are written the way they read, and names are matched when the files are read, so the text is never rewritten:

1. **Normalize the name.** Lowercase, hyphenate, and make the last word singular, so `Green Onions` becomes `green-onion`.
2. **Look it up.** An exact name or alias matches silently. `green-onion` is `scallion`.
3. **Suggest close matches.** If there's no match, `validate` names the line and the nearest entries by spelling and shared words. `pork butt` suggests `pork-shoulder`, and `chipotle` suggests `chipotle-in-adobo`.
4. **Ask Claude to decide.** Claude either adds an alias (`vocab alias cilantro coriander`) or a new entry (`vocab add guajillo-chile --section pantry`).

Claude makes the judgment call (is coriander the same as cilantro?), and the script does the bookkeeping. It puts the entry in the right section in alphabetical order and refuses duplicates. Every alias added means fewer questions next time.

## 2. The skill

`.agents/skills/recipes/` holds `SKILL.md` (the workflow), `references/format.md` (the file formats and house style), and `scripts/`: `recipes.py` and the small `cookbook` package behind it. It needs Python 3.10+ and PyYAML, which Claude's and ChatGPT's sandboxes already have, so it runs as-is in Claude Code, Codex, claude.ai, ChatGPT, and CI. Where PyYAML is missing, `uv run --with pyyaml scripts/recipes.py` covers it.

The script reads a local checkout when it's inside one. Anywhere else, it downloads the published `index.json`, so most work doesn't need the repo at all:

| Command | Does | Needs the repo? |
|---|---|---|
| `find` | Search by words, course, cuisine, protein, ingredient, time, or last cooked | No |
| `show <name\|file>` | Show a recipe, or preview a draft, as it'll look on the site | No |
| `grocery <names…>` | Combine recipes into one shopping list, grouped by section | No |
| `validate [files…]` | Check drafts against the vocab, exactly as CI will | No |
| `vocab find` / `vocab list` | Look up ingredient names | No |
| `export <names…>` | Print recipes as schema.org Recipe JSON-LD, for other apps | No |
| `save <files…>` | Check drafts together, name them from their titles, and file them | Yes |
| `vocab add` / `vocab alias` | Add an ingredient or alias | Yes |
| `plan` / `cooked` | Write a plan or mark a meal as cooked | Yes |
| `build [dir]` | Check everything and write the site bundle | Yes |

Saving anything means pushing, which needs a session with this repo attached. It's tiny, so cloning takes seconds. A typical session validates everything first, then pushes once, so CI runs once.

For regular chats in Claude or ChatGPT, every CI run publishes the skill folder as the `recipes-skill` artifact, ready to upload; see [Setting up the chat apps](#setting-up-the-chat-apps). The index records its format version, and the skill refuses to validate against a format it doesn't know, so an outdated upload says so instead of quietly disagreeing with CI.

## 3. The website

The recipe pages live in [collinmurch.github.io](https://github.com/collinmurch/collinmurch.github.io), so they share its theme, build, and checks. The site never parses Cooklang or reads this repo's files. Everything it needs comes in one bundle that this repo builds:

```
index.json      every recipe parsed, the plans, and the vocab
jsonld/*.json   each recipe as schema.org Recipe JSON-LD, to embed in its page
sources/*.cook  the raw files, for "view source" links
```

[`index.schema.json`](.agents/skills/recipes/references/index.schema.json) documents every field of `index.json`, and the tests hold every build to it. Display strings come ready to use: each ingredient's `line` ("1.5 kg pork shoulder (cubed)") and each step's `text`. So the site, a Mela converter, or a chat can show recipes without re-deriving anything, and the structured fields are there for scaling and highlighting. The JSON-LD leaves out the page `url`, which the site adds.

On every push to `main` that passes, CI uploads the bundle as the `site` artifact. It then sends the site a `recipes-updated` dispatch with the run ID, and the site downloads that artifact, renders, and deploys:

- `/recipes`: every recipe, filterable by course, cuisine, and protein
- `/recipes/<name>`: a recipe page, plus its raw `.cook` source
- `/recipes/plans/<id>`: a plan and its grocery list
- `/recipes/index.json`: the bundle's index, as-is, for the skill to search and validate against
- `/recipes/feed.xml` and `/recipes/all.melarecipes`: for Mela

The bundle is the whole contract. New fields can appear at any time; the schema number changes only when a field is removed or changes meaning.

## 4. Mela

[Mela](https://mela.recipes) is the app we cook from. It gets recipes three ways:

- **Feed.** Mela subscribes to `/recipes/feed.xml`, and new recipes appear ready to add with one tap.
- **Share sheet.** Every page includes standard recipe markup, so any recipe can be saved from Safari.
- **Bulk import.** `all.melarecipes` loads the whole collection at once.

Each recipe's Mela ID is its page URL, so importing the same recipe twice doesn't create a duplicate. This only goes one way: edits made in Mela don't come back here.

## Setting up the chat apps

To use the skill in regular chats, download the latest `recipes-skill` artifact from a CI run and upload the `recipes` folder as a skill. Then let the app reach `collinmurch.com`, so the skill can download `index.json`:

- **Claude:** in Settings → Capabilities, turn on **Allow network egress**. Set **Domain allowlist** to **None**, and add `collinmurch.com` under **Additional allowed domains**. That's the most restrictive setting that still works.
- **ChatGPT:** in Settings → Data controls, turn on **Work network access**.

Re-upload the skill whenever it changes. Recipes don't need a re-upload, since the skill always reads the latest index.

## Working locally

```
uv sync                                        # once: Python, PyYAML, pytest, ruff, and ty in .venv
uv run ruff check --fix && uv run ruff format  # lint and format, as CI checks
uv run ty check                                # type-check
uv run pytest                                  # the tool's tests and a check of the whole collection
alias recipes="uv run .agents/skills/recipes/scripts/recipes.py"
recipes validate                               # just check the collection
recipes find --protein pork
recipes show jambalaya --servings 6
recipes build                                  # write the bundle to dist/ (ignored by git)
recipes find --source dist                     # read from the built index, the way claude.ai does
```

The conformance tests compare the parser with the [`cook` CLI](https://cooklang.org/cli/) when it's installed. CI skips them, so it doesn't spend time installing it.

## Cost

Free. GitHub Actions and Pages are free for the public site repo, and this private repo's checks fit easily in GitHub's free minutes. One fine-grained token, `SITE_TOKEN`, is stored in both repos. It can read this repo's contents and Actions artifacts, and it can write the site repo's contents, which is what sending it a dispatch requires.
