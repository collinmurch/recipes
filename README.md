# Recipes

A personal recipe collection and weekly meal planner, built so an AI can do the planning and bookkeeping while the recipes stay as plain files we own.

The goal is to cook 3–4 planned dinners a week from a single grocery trip, reusing ingredients across meals so less goes to waste.

## How it works

```
Claude (with this repo attached)
  └─ writes recipes and weekly plans, previews and checks them, then pushes
       └─ this repo's CI runs the check and pings the website repo
            └─ collinmurch.com rebuilds, pulling in the latest recipes
                 ├─ /recipes: readable recipe pages, themed like the rest of the site
                 └─ /recipes/feed.xml: an RSS feed that Mela subscribes to
```

This repo holds content only: recipes, plans, the ingredient dictionary, the parser, and the Claude skill. The pages themselves live in [collinmurch.github.io](https://github.com/collinmurch/collinmurch.github.io), so the recipes share its theme, build, and checks. Claude only ever needs access to this repo.

## Layout

```
recipes/*.cook              one file per recipe or drink (Cooklang)
plans/*.md                  one file per week
vocab.yaml                  the ingredient dictionary
lib/cook.js                 turns a .cook file into a recipe object
scripts/recipes.js          the command-line tool Claude uses
.claude/skills/recipes/     instructions for Claude
.github/workflows/check.yml validates, then triggers the site rebuild
```

## Recipes are `.cook` files

Recipes use [Cooklang](https://cooklang.org), a plain-text recipe format. Ingredients are marked inline in the steps, like `@cilantro{1%bunch}`, and equipment like `#dutch oven{}`. That means the ingredient list, quantities, and equipment are read from the steps, not written out twice.

The frontmatter at the top holds only what can't be worked out from the steps: title, course (main, side, dessert, or drink), cuisine, servings, active and total time, how well it keeps as leftovers, tags, rating, and source.

## The ingredient dictionary

`vocab.yaml` is the one list of ingredient names used across every recipe, grouped by store section. Two sections never appear on a shopping list: `pantry` (staples we always have) and `bar` (bottles that last for months). Names can have aliases, so "green onion" becomes `scallion` automatically.

```yaml
produce:
  cilantro: {}
  scallion: { aka: [green onion] }
meat:
  pork-shoulder: { protein: pork }
pantry:
  cumin: {}
bar:
  rye: {}
```

Using the same name everywhere is what lets us spot shared ingredients between recipes and add up quantities for a shopping list.

## Weekly plans

Each week is a markdown file listing the chosen recipes, when each one was cooked, any notes, and what we spent. The page body holds the combined grocery list, grouped by store section.

"Last cooked" is worked out from these plans, so recipe files never need editing just because we made something.

## One parser, used everywhere

`lib/cook.js` is a small, dependency-free parser for the parts of Cooklang we use. It turns a `.cook` file into one recipe object: frontmatter, an ingredient list with amounts and store sections, equipment, and steps split into plain text, ingredients, and timers.

Everything is built from that object: the website page, the Mela files, the shopping lists, and Claude's previews. Because the website imports the parser straight from this repo, a recipe that looks right in a preview will look the same on the site.

## Finding recipes without loading them all

There's no index file to keep up to date. `find` reads every recipe's frontmatter and the plans directly, which takes milliseconds even with hundreds of recipes, and prints only the matches. Claude filters first, then opens only the few recipes it picks.

For readers without a shell, the site build also publishes `/recipes/index.json`, a short summary of every recipe.

## The script

`scripts/recipes.js` runs with Bun or plain Node and has no dependencies, so it works anywhere:

- `find`: filter by course, protein, cuisine, time, or how recently we cooked something
- `new`: tidy up a new recipe (fix ingredient names, name the file) and add it
- `preview`: show a recipe exactly as the site will, as markdown in the chat
- `plan`: write a week's plan with a combined, section-grouped grocery list
- `cooked`: mark a recipe as cooked this week
- `check`: confirm every recipe parses, every ingredient is in the dictionary, and every plan points at real recipes

Claude chooses what to cook and writes the recipe text. The script handles anything that has to be exactly right, like names, totals, and file paths.

## The Claude skill

The skill in `.claude/skills/recipes/` describes the workflow: find, choose, write, preview, check, and push. It also explains how Cooklang maps to the recipe object, so Claude can show you a recipe in the chat before anything is pushed.

Every change gets previewed and checked locally first, and a session's changes go out in one push. That keeps CI to one short run per session. The same skill folder can be uploaded to Claude so regular chats know the conventions too.

## The website side

In `collinmurch.github.io`, the build checks out this repo into `content/recipes` and uses `lib/cook.js` while prerendering:

- `/recipes`: everything, with filters by course, cuisine, and protein
- `/recipes/<name>`: one recipe, rendered by a Svelte component from the recipe object
- `/recipes/plans/<week>`: a weekly plan and its grocery list
- `/recipes/feed.xml`: the newest recipes, for Mela
- `/recipes/all.melarecipes`: the whole collection, for importing into Mela at once
- `/recipes/index.json`: the summary for other tools

The parser only runs at build time, so recipe pages ship as plain HTML. The site's existing bundle budgets, lint, and tests cover the recipe pages too.

## Mela

[Mela](https://mela.recipes) is the app we cook from. It gets recipes from the site in three ways:

1. **Feed:** Mela subscribes to `/recipes/feed.xml`, and new recipes show up in the app ready to add with one tap.
2. **Share sheet:** every recipe page includes standard recipe markup (schema.org JSON-LD), so any page can be saved to Mela from Safari.
3. **Bulk file:** `all.melarecipes` is a zip of Mela's own JSON recipe format, built from the recipe objects, for loading the whole collection at once.

Each recipe's Mela ID is its page URL, which matches what Mela uses when it imports from the web, so the same recipe isn't added twice.

This is one-way: edits made inside Mela don't come back here. Changes go through the repo.

## CI

1. A push here runs `check`. Pushes that only change docs are skipped.
2. If it passes, the workflow sends a `recipes-updated` event to the website repo.
3. The website rebuilds and deploys to GitHub Pages.

A bad recipe never reaches the site or Mela, whoever added it. This repo can stay private: one fine-grained GitHub token, limited to these two repos, lets the site read it and lets this repo trigger the rebuild. Everything runs on GitHub's free tier.
