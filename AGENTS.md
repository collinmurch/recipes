# Agents

This repo is our recipe collection. All recipe work (writing, porting, editing, vocab, plans, logging meals) follows the `recipes` skill: read [`SKILL.md`](.agents/skills/recipes/SKILL.md) and the references it points to before changing content. It is the single source for workflow and format rules, so don't restate them elsewhere.

- Use the skill's script for anything it has a command for (`save`, `vocab add`, `vocab alias`, `plan`, `cooked`) instead of editing those files by hand.
- Before pushing, run `validate` with no files. Commit the session's work once with a plain message and push to `main`. CI runs the same checks and publishes the site.
- When changing the tool itself, run what CI runs: `uv run ruff check`, `uv run ruff format --check`, `uv run ty check`, `uv run pytest`.
- The site repo only renders the bundle CI sends it. Don't edit it from here.
