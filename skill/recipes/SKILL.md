---
name: recipes
description: Our recipe collection. Use for anything about recipes, cooking, meals, drinks, or groceries, such as dinner ideas, meal plans, shopping lists, writing or porting a recipe, or logging what we made.
---

# Recipes

Our recipes live in the GitHub repo [collinmurch/recipes](https://github.com/collinmurch/recipes), and its `AGENTS.md` covers everything else: the workflow, the format, and the tool. Always work from a checkout, never from memory.

1. Not in a checkout (one has `AGENTS.md` and `vocab.yaml`)? Run `git clone --depth 1 https://github.com/collinmurch/recipes` and work inside the new folder.
2. Follow the repo's agent instructions in `AGENTS.md` or `CLAUDE.md` (the same file). Most harnesses load one of them automatically; read `AGENTS.md` only if neither is in your context yet.
3. Before any work that changes files, run `python3 scripts/recipes.py publish --check`. A public repo clones without access, so this is the only early sign that saving will fail.
4. If the clone or the check fails, ask the user to give this session access to `collinmurch/recipes`. If they'd rather not, finish the work and hand over the changes at the end.
