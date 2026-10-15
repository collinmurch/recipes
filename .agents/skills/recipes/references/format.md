# Recipe format

## A complete example

```
---
title: Pork Carnitas
course: main
cuisine: mexican
servings: 4
time_active: 30
time_total: 180
leftovers: great
tags: [weekend, freezer-friendly]
pairs: [salsa-verde]
source: https://www.seriouseats.com/the-food-lab-real-deal-mexican-carnitas
---

Cut @pork shoulder{1.5%kg} into 2-inch chunks. Season with @salt{2%tsp} and @cumin{1%tsp}.

Heat @lard{2%tbsp} in a #dutch oven{} over medium-high. Brown the pork in batches, ~{8%minutes} per batch.

Serve in warm @corn tortillas{12} with @cilantro{1%bunch}(chopped) and @?limes{2}(in wedges).

> Leftovers: crisp a portion in a hot skillet instead of microwaving it.
```

## Frontmatter

| Key | Required | Value |
|---|---|---|
| `title` | yes | The name. The file name comes from it: "Pork Carnitas" becomes `pork-carnitas.cook` |
| `course` | yes | `breakfast`, `main`, `side`, `sauce`, `snack`, `dessert`, or `drink`. Drinks are filed in `drinks/` |
| `servings` | yes | A number |
| `time_total` | yes, except drinks | Whole minutes, start to plate, including passive time |
| `time_active` | no | Whole minutes of hands-on work |
| `cuisine` | no | One lowercase word or hyphenated phrase: `mexican`, `southeast-asian` |
| `leftovers` | no | How it keeps: `great` (as good or better the next day), `good`, or `poor` |
| `tags` | no | Lowercase words: `weeknight`, `one-pot`, `freezer-friendly`, `date-night`, `make-ahead` |
| `pairs` | no | File names of dishes that go with it, usually sides for a main |
| `rating` | no | 1 to 5, only once we've made it |
| `source` | no | A URL, or text like "Grandma" |
| `description` | no | One sentence for the index page |

Leave out anything the steps already say. Ingredients, equipment, and protein all come from the steps and the vocab.

## Cooklang we use

- `@salt` is a one-word ingredient. A name with spaces needs braces: `@olive oil{}`. Without them, `@olive oil` means an ingredient called "olive".
- `@flour{2%cups}` gives a quantity and unit. Quantities can be `2`, `1.5`, `1/2`, `1 1/2`, or text like `2-3`. Text doesn't scale. `{=1%tsp}` never scales.
- `@onion{1}(diced)` adds a note: prep, size, or a substitute.
- `@?cilantro{}` marks an ingredient optional, such as a garnish. It shows as optional on grocery lists.
- `#dutch oven{}` is equipment. `~{10%minutes}` is a timer; give a range as text: `~{3-4%minutes}`.
- A blank line separates steps. A paragraph starting with `>` is a note.
- `== Sauce ==` on its own line starts a section. Its ingredients are listed under that heading, and step numbers restart. Use sections only when a part is its own thing, like a vinaigrette or a sauce.
- `-- comment` and `[- comment -]` are ignored.

Units: `tsp`, `tbsp`, `cup`, `fl oz`, `ml`, `l`, `g`, `kg`, `oz`, `lb`, plus counts like `clove`, `bunch`, `can`, `stalk`, `slice`, `sprig`, `pinch`, and `dash`. Any common spelling works ("tablespoons", "lbs"). A bare number counts whole items: `@limes{2}`.

## Ingredient names

Write ingredients the way the step reads, then let the vocab do the matching. `@green onions{2}` and `@scallion{1}` both count as `scallion` on the grocery list.

- Name the thing you'd buy, and put everything else in the note: `@chicken thighs{4}(bone-in, skin-on)`, not `@bone-in skin-on chicken thighs{4}`.
- Tag an ingredient once, where it's first used, with its full amount. Later mentions are plain text: "Return the pork to the pot."
- If a part is used twice, tag each use with its own amount (`@chicken broth{1 1/2%cups}` for the quinoa, `@chicken broth{1/4%cup}` for the glaze). The amounts are added together.
- When only part of an item is used, say so in the prose: "the juice of @lime{1}", "the zest of @lemon{1}".
- Salt and pepper to taste are just `@salt` and `@black pepper{}`.

## Vocab

`vocab.yaml` holds every ingredient name once, in store order. The grocery list follows the same order.

```yaml
produce:
  scallion: {aka: [green onion, spring onion]}
meat:
  pork-shoulder: {aka: [pork butt], protein: pork}
pantry:
  cumin: {}
```

Names are lowercase, hyphenated, and singular. `aka` lists other names for the same thing; plurals and hyphens resolve automatically. `protein` (`chicken`, `beef`, `pork`, `fish`, and so on) drives `find --protein`. Items in `pantry` and `bar` are things we always have, so they're left off shopping lists and shown as a checklist instead.

The sections are `produce`, `meat`, `seafood`, `deli`, `dairy`, `bakery`, `aisles` (shelf-stable groceries we buy as needed), `frozen`, `liquor` (wine and beer for cooking), `pantry` (spices, oils, vinegars, staples), and `bar` (spirits, bitters, garnishes). Always edit the vocab with `vocab add` and `vocab alias`, never by hand; they keep it sorted and refuse duplicates.

## Plans

`plans/<YYYY-MM-DD>.md` covers the week starting that Monday. `plans/<YYYY-MM-DD>-<name>.md` is a one-off, such as `2026-12-24-christmas-eve`.

```
---
title: Soup week
spent: 142.18
extras: [paper towels, sparkling water]
meals:
  - recipe: pork-carnitas
    date: 2026-10-13
    servings: 6
    cooked: 2026-10-13
    note: Doubled the lime.
  - recipe: jambalaya
---

Free-form notes about the week.
```

Only `meals[].recipe` is required. `date` is when it's planned, and `cooked` is when it was actually made. Leave `cooked` out until then. The grocery list isn't stored: `grocery --plan <id>` and the site build it from the uncooked meals plus `extras`.

## House style

Steps are short imperatives, one action group per paragraph, with doneness cues ("until golden, ~{5%minutes}") instead of bare times. Put tips, storage, and substitutions in a `>` note at the end. Leave out preamble, "why this works", and serving pep talk.
