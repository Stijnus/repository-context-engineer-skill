# Repository Context Engineer Skill

A Claude Code skill that builds a persistent project context pack for a repository so an agent can understand structure, entrypoints, commands, boundaries, and likely ownership before it starts broad searching.

## Why this exists

Agents often waste tokens and time rediscovering the same repository on every task:

- searching for likely files
- grepping repeatedly across the whole codebase
- opening too many files just to find the real entrypoint or owning module
- missing important configs or conventions because they were never made explicit

This skill addresses that by generating a reusable navigation layer under `.claude/project-context/`.

## What it generates

The builder writes a small set of durable artifacts:

- `OVERVIEW.md`
- `STACK.md`
- `COMMANDS.md`
- `ENTRYPOINTS.md`
- `AREAS.md`
- `IMPORTANT_FILES.md`
- `SYMBOL_INDEX.md`
- `DIRECTORY_TREE.txt`
- `FILES.csv`
- `MANIFEST.json`

## Install

Place this skill in either:

- `~/.claude/skills/repository-context-engineer/`
- or `.claude/skills/repository-context-engineer/` inside a repo

Required files:

- `SKILL.md`
- `scripts/build_context_pack.py`

Optional:

- `examples/settings.snippets.jsonc`

## Use

Typical prompts:

- “Understand this repo before making changes.”
- “Map the codebase and tell me where auth lives.”
- “Build project context first, then implement the billing fix.”
- “Stop searching blindly and create a reusable repo context pack.”

## Workflow

1. Check whether `.claude/project-context/` exists.
2. If missing or stale, run the builder.
3. Read the generated pack first.
4. Narrow the task to the likely subsystem.
5. Read only the most relevant source files.
6. Refresh the pack after structural changes.

## Notes

This is intentionally different from a full repo packer. It is not trying to dump the entire codebase into a single prompt. It is trying to produce a compact, durable operating model the agent can reuse across tasks.

A strong setup combines:

- `CLAUDE.md` for conventions and instructions
- this skill for structure and routing
- native repo search for precise retrieval
