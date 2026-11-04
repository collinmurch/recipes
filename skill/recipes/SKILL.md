---
name: recipes
description: Our recipe collection. Use for anything about recipes, cooking, meals, drinks, or groceries, such as dinner ideas, meal plans, shopping lists, writing or porting a recipe, or logging what we made.
---

# Recipes

Our recipes live in the GitHub repo [collinmurch/recipes](https://github.com/collinmurch/recipes), and its `AGENTS.md` covers everything else: the workflow, the format, and the tool. Always work from a checkout, never from memory.

1. In a checkout already (it has `AGENTS.md` and `vocab.yaml`)? Read `AGENTS.md` and follow it.
2. Otherwise, run `git clone --depth 1 https://github.com/collinmurch/recipes`, work inside the new folder, and follow its `AGENTS.md`.
3. If the clone fails, stop and tell the user what this session needs:
   - **Claude Code or Codex:** nothing locally. In the cloud, add the `collinmurch/recipes` repo to the session or environment, and allow `github.com` if internet access is limited.
   - **Claude app:** turn on code execution and network access in Settings → Capabilities, and allow `github.com`.
   - **ChatGPT:** its sandbox can't reach GitHub, so this skill can't run there. Suggest Codex or Claude instead.
4. Before any work that changes files, run `python3 scripts/recipes.py publish --check`. Cloning a public repo always works, so this is the only early sign that saving will fail. If it fails, tell the user now that this session can't push, and that you'll hand over the changes at the end.
