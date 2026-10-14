# Recipes

A personal recipe collection and weekly meal planner, built so an AI can do the planning and bookkeeping while the recipes stay as plain files we own.

The goal is to cook 3–4 planned dinners a week from a single grocery trip, reusing ingredients across meals so less goes to waste.

## How it works

```
Claude (with this repo attached)
  └─ writes recipes and weekly plans, runs the checks, commits to main
       └─ GitHub Actions validates and builds the site
            └─ recipes.collinmurch.com
                 ├─ readable recipe pages on any phone
                 └─ an RSS feed that Mela subscribes to
```

The repo is the source of truth. The site, the search index, and the Mela files are all generated from it.

## Layout

```
recipes/*.cook          one file per recipe (Cooklang)
plans/*.md              one file per week
vocab.yaml              the ingredient dictionary
.claude/skills/recipes/ instructions and scripts for Claude
src/                    the SvelteKit site
```

## Recipes are `.cook` files

Recipes use [Cooklang](https://cooklang.org), a plain-text recipe format. Ingredients are marked inline in the steps, like `@cilantro{1%bunch}`, and equipment like `#dutch oven{}`. That means the ingredient list, quantities, and equipment are read from the steps, not written out twice.

The frontmatter at the top holds only what can't be worked out from the steps: title, cuisine, servings, active and total time, how well it keeps as leftovers, tags, rating, and source.

## The ingredient dictionary

`vocab.yaml` is the one list of ingredient names used across every recipe, grouped by store section. A `pantry` section holds staples we always have, so they never show up on a shopping list. Names can have aliases, so "green onion" becomes `scallion` automatically.

```yaml
produce:
  cilantro: {}
  scallion: { aka: [green onion] }
meat:
  pork-shoulder: { protein: pork }
pantry:
  cumin: {}
```

Using the same name everywhere is what lets us spot shared ingredients between recipes and add up quantities for a shopping list.

## Weekly plans

Each week is a markdown file listing the chosen recipes, when each one was cooked, any notes, and what we spent. The page body holds the combined grocery list, grouped by store section.

"Last cooked" is worked out from these plans, so recipe files never need editing just because we made something.

## The index

The build generates `index.json`: one short entry per recipe with its cuisine, protein, times, leftovers, rating, last-cooked date, and what needs buying. The index is never edited by hand.

Claude reads the index to search instead of opening every recipe. A typical planning session reads the index, filters it down, then opens only the few recipes it picks, so it stays light even with hundreds of recipes.

## The skill and script

The skill in `.claude/skills/recipes/` describes the workflow: search the index, choose meals, write recipes, build the plan, check, and commit. It ships with one dependency-free script that runs with Bun or Node, so it works even where nothing can be installed:

- `find`: filter recipes by protein, time, how recently we cooked them, and so on
- `new`: tidy up a new recipe (fix ingredient names, name the file) and add it
- `plan`: write a week's plan with a combined, section-grouped grocery list
- `cooked`: mark a recipe as cooked this week
- `check`: confirm every recipe parses, every ingredient is in the dictionary, and every plan points at real recipes

Claude chooses what to cook and writes the recipe text. The script handles anything that has to be exactly right, like names, totals, and file paths.

The same skill folder can also be uploaded to Claude so regular chats know the conventions.

## The site

The site uses the same stack as collinmurch.com: Bun, SvelteKit with the static adapter, Svelte 5, and Tailwind. It deploys to GitHub Pages at `recipes.collinmurch.com`.

Recipe pages are built by parsing each `.cook` file with Cooklang's parser and rendering it through a Svelte component. Plans are markdown and render like blog posts. The site includes:

- A page per recipe, plus lists by cuisine and protein
- A page per weekly plan with its grocery list
- `feed.xml`, the newest recipes, for Mela
- `all.melarecipes`, the full collection, for importing into Mela in one go

## Mela

[Mela](https://mela.recipes) is the app we cook from. It gets recipes from the site in three ways:

1. **Feed:** Mela subscribes to `feed.xml`, and new recipes show up in the app ready to add with one tap.
2. **Share sheet:** every recipe page includes standard recipe markup (schema.org JSON-LD), so any page can be saved to Mela from Safari.
3. **Bulk file:** `all.melarecipes` is a zip of Mela's own JSON recipe format, generated from the `.cook` files, for loading the whole collection at once.

Each recipe's Mela ID is its page URL, which matches what Mela uses when it imports from the web, so the same recipe isn't added twice.

This is one-way: edits made inside Mela don't come back here. Changes go through the repo.

## Checks

GitHub Actions runs `check` and the site build on every push, and the site only deploys if both pass. A bad recipe can't reach the site or Mela, whoever added it.
