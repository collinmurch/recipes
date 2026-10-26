---
name: recipes
description: Our recipe collection. Use for anything about recipes, cooking, meals, drinks, or groceries, such as dinner ideas, meal plans, shopping lists, writing or porting a recipe, or logging what we made.
---

# Recipes

Our recipes live in the GitHub repo [collinmurch/recipes](https://github.com/collinmurch/recipes), and its `AGENTS.md` covers everything else: the workflow, the format, and the tool. Always work from a checkout, never from memory.

1. In a checkout already (it has `AGENTS.md` and `vocab.yaml`)? Read `AGENTS.md` and follow it.
2. Otherwise, run `git clone --depth 1 https://github.com/collinmurch/recipes`, work inside the new folder, and follow its `AGENTS.md`.
3. If the clone fails, stop and tell the user what this session needs:
   - **Claude Code:** add the `collinmurch/recipes` repo to the session.
   - **Claude app:** turn on code execution and network access in Settings → Capabilities, and allow `github.com`.

Reading and planning only need the clone. Saving needs a push to `main`. Without push access, finish the work, then hand the user the files and commands so a session with access can save them.
