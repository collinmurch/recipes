# Recipes

Plan meals with Claude, keep the recipes as plain files we own, and cook from a nice app on the phone.

You work out a dinner or drink with Claude. Claude saves it as a `.cook` file in this repo. The repo rebuilds the recipe pages on collinmurch.com, and the site's RSS feed sends new recipes to Mela on iOS. Claude can also search everything we've saved, so a week of meals can share ingredients and come from one grocery trip.

It's all free apart from the domain, and Claude only has access to this one repo.

```
Claude ──push──▶ this repo ──check passes──▶ collinmurch.com/recipes ──RSS──▶ Mela
   ▲                                                   │
   └──────────── searches the published index ─────────┘
```

There are four parts: this repo, the Claude skill, the website, and Mela.

## 1. This repo

The source of truth. It holds content only, with no website code.

```
recipes/*.cook            recipes and drinks
plans/*.md                one file per week
vocab.yaml                every ingredient name, grouped by store section
.claude/skills/recipes/   the skill: instructions, the parser, and the script
```

**Recipes** are written in [Cooklang](https://cooklang.org). Ingredients are marked inside the steps (`@cilantro{1%bunch}`), so the ingredient list, amounts, and equipment come from the steps instead of being typed twice. The frontmatter holds only what the steps can't tell you: title, course (main, side, dessert, or drink), cuisine, servings, times, how well it keeps, tags, rating, and source.

**Plans** list the week's recipes, when each was cooked, notes, and what we spent, with the grocery list underneath. "Last cooked" comes from the plans, so a recipe file never changes just because we made it.

**Vocab** is the dictionary of ingredient names. Each name appears once, under its store section. `pantry` and `bar` hold things we always have, so they're left off shopping lists.

```yaml
produce:
  cilantro: {}
  scallion: { aka: [green onion, spring onion] }
meat:
  pork-shoulder: { protein: pork }
pantry:
  cumin: {}
bar:
  rye: {}
```

### Adding ingredients

One name per ingredient is what makes shared ingredients and shopping-list totals work, so adding to the vocab should be easy and hard to get wrong. When a recipe uses an ingredient, the script works through these steps:

1. **Normalize the name.** It lowercases, hyphenates, and makes the word singular, so `Green Onions` becomes `green-onion`.
2. **Look it up.** An exact name or alias match is replaced silently. `green-onion` becomes `scallion`.
3. **Suggest close matches.** If there's no match, it lists the nearest names by spelling and shared words. `pork-butt` suggests `pork-shoulder`, and `chipotle` suggests `chipotle-in-adobo`.
4. **Ask Claude to decide.** Claude either adds an alias (`vocab alias scallion "green onion"`) or a new entry (`vocab add guajillo --section pantry`).

Claude makes the judgment call (is coriander the same as cilantro?), and the script does the bookkeeping. It puts the entry in the right section in alphabetical order and refuses duplicates. Every alias added means fewer questions next time.

**On every push**, CI runs the same check the skill runs. If it passes, CI tells the website to rebuild. A bad recipe never reaches the site.

## 2. The Claude skill

`.claude/skills/recipes/` holds `SKILL.md` (the workflow and conventions), `cook.js` (the parser), and `recipes.js` (the script). Both run with Node or Bun and have no dependencies. The website uses the same parser, so a preview in chat matches the published page.

The script reads from a local clone when there is one, or from the live site when there isn't, so most work doesn't need the repo at all:

| Command | Does | Needs the repo? |
|---|---|---|
| `find` | Search by course, protein, cuisine, time, or last cooked | No |
| `show <name>` | Show a recipe as it'll look on the site | No |
| `grocery <names…>` | Combine recipes into one shopping list, grouped by section | No |
| `validate <file>` | Check a draft against the live vocab, exactly as CI will | No |
| `vocab add` / `vocab alias` | Add an ingredient or alias | Yes |
| `new <file>` | Fix the ingredient names, name the file, and save it | Yes |
| `plan` / `cooked` | Write a week's plan or mark a meal as cooked | Yes |

Saving anything means pushing, which needs a session with this repo attached. It's tiny, so cloning takes seconds. A typical session validates everything first, then pushes once, so CI runs once.

The same folder can be uploaded to Claude as a skill for regular chats. CI zips it on every change, so updating is one re-upload. The site publishes the parser version, and the skill refuses to validate if it's out of date.

## 3. The website

The recipe pages live in [collinmurch.github.io](https://github.com/collinmurch/collinmurch.github.io), so they share its theme, build, and checks.

When this repo pings it, the site checks out the latest recipes, parses them at build time, and deploys to GitHub Pages:

- `/recipes`: every recipe, filterable by course, cuisine, and protein
- `/recipes/<name>`: a recipe page, plus its raw `.cook` source
- `/recipes/plans/<week>`: a week's plan and grocery list
- `/recipes/index.json` and `/recipes/vocab.json`: what the skill searches and validates against
- `/recipes/feed.xml` and `/recipes/all.melarecipes`: for Mela

The parser only runs during the build, so the pages ship as plain HTML.

## 4. Mela

[Mela](https://mela.recipes) is the app we cook from. It gets recipes three ways:

- **Feed.** Mela subscribes to `/recipes/feed.xml`, and new recipes appear ready to add with one tap.
- **Share sheet.** Every page includes standard recipe markup, so any recipe can be saved from Safari.
- **Bulk import.** `all.melarecipes` loads the whole collection at once.

Each recipe's Mela ID is its page URL, so importing the same recipe twice doesn't create a duplicate. This only goes one way: edits made in Mela don't come back here.

## Cost

Free. GitHub Actions and Pages are free for the public site repo, and this private repo's checks fit easily in GitHub's free minutes. One fine-grained GitHub token, limited to these two repos, lets the site read this repo and lets this repo trigger the rebuild.
