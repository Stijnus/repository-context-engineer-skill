---
name: repository-context-engineer
description: Build and maintain a persistent project context pack for software repositories. Use when working in a new or large codebase, when a task requires understanding architecture before editing, when file discovery is expensive, or when repeated grep/search/read cycles are likely. Creates reusable structure, commands, entrypoints, area maps, and symbol indexes so future tasks can target the correct files faster.
allowed-tools: Read, Write, Edit, MultiEdit, Bash, Glob, Grep, LS
---

# Repository Context Engineer

This Skill exists to reduce wasteful repo-wide searching and improve code changes by giving Claude a durable, navigable understanding of the repository before implementation starts.

The goal is **not** to dump the whole repo into context. The goal is to create and maintain a **project context pack** under `.claude/project-context/` that acts as reusable operating knowledge for future tasks.

## When to use this Skill

Use this Skill proactively when any of the following are true:

- The repository is unfamiliar.
- The task references a feature or subsystem but not exact files.
- The repo is large enough that repeated `grep`, `find`, and `read` cycles are expensive.
- The user wants more reliable edits with less file hunting.
- The codebase lacks clear `CLAUDE.md` project memory.
- You notice yourself guessing where logic lives.
- The task spans multiple folders, services, or apps.

Do **not** use this Skill for tiny one-file edits where the relevant file is already known.

## Desired outcome

Create a small set of durable context artifacts that answer these questions quickly:

1. What kind of project is this?
2. How is it structured?
3. Which files are likely entrypoints and key configs?
4. Which commands matter for build, test, lint, and run?
5. Which top-level areas own which responsibilities?
6. Where are the important symbols and routes defined?
7. Which files are most likely relevant to the current task?

## Core operating rule

Before broad searching, check whether `.claude/project-context/` already exists and is still likely usable.

Start by reading only these files if present:

- `.claude/project-context/OVERVIEW.md`
- `.claude/project-context/STACK.md`
- `.claude/project-context/COMMANDS.md`
- `.claude/project-context/ENTRYPOINTS.md`
- `.claude/project-context/AREAS.md`
- `.claude/project-context/SYMBOL_INDEX.md`

Only expand into raw source files after these artifacts narrow the likely target area.

## Workflow

### 1. Decide whether the context pack is missing or stale

Treat the context pack as **missing or stale** when:

- `.claude/project-context/` does not exist.
- The repository structure appears to have changed significantly.
- The task is in a subsystem that is absent from the pack.
- The pack predates a large refactor or newly added app/service.

### 2. Build or refresh the context pack

From the repository root, run:

```bash
python .claude/skills/repository-context-engineer/scripts/build_context_pack.py .
```

If the skill is installed globally instead of in the repo, adapt the script path accordingly.

This script writes deterministic markdown and text artifacts into:

- `.claude/project-context/`

These artifacts are lightweight and reusable. They are intended to be read before touching source code.

### 3. Read the pack in layers

Read in this order unless the task clearly needs something else:

1. `OVERVIEW.md`
2. `STACK.md`
3. `COMMANDS.md`
4. `ENTRYPOINTS.md`
5. `AREAS.md`
6. `SYMBOL_INDEX.md`
7. `DIRECTORY_TREE.txt`
8. `IMPORTANT_FILES.md`

Do not load everything at once if not needed.

### 4. Route the task before reading code

After reading the pack, identify:

- likely subsystem
- likely owning folder(s)
- likely entrypoints
- likely tests
- likely configuration files

Then do targeted reads/searches only in those areas.

### 5. State the file hypothesis before editing

Before making code changes, explicitly form a short working hypothesis in your reasoning or notes:

- which files likely need changes
- why those files were selected
- what nearby tests/configs may also need updates

If the hypothesis is weak, improve it with targeted reads rather than broad repo scans.

### 6. Update the context pack after structural changes

Re-run the builder after:

- adding new apps/services/packages
- renaming important folders
- moving entrypoints
- adding major commands/scripts
- adding new route groups or API surfaces

## Editing constraints

- Never overwrite source files when generating context.
- Only write inside `.claude/project-context/` unless the user asked for code changes.
- Keep the pack concise and navigable.
- Prefer deterministic extraction over speculative summaries.
- If a signal is uncertain, label it as probable rather than authoritative.

## What the context pack should contain

The builder should maintain these files:

- `OVERVIEW.md` — repo identity, size, detected stacks, likely apps/services
- `STACK.md` — languages, frameworks, package managers, tooling hints
- `COMMANDS.md` — build/test/lint/dev commands discovered from config files
- `ENTRYPOINTS.md` — likely runtime entrypoints and important configs
- `AREAS.md` — top-level folders and inferred responsibilities
- `IMPORTANT_FILES.md` — files worth reading first for orientation
- `SYMBOL_INDEX.md` — high-signal top-level symbols/functions/classes/routes
- `DIRECTORY_TREE.txt` — trimmed directory tree for navigation
- `MANIFEST.json` — machine-readable generation metadata

## Heuristics to prefer

Use heuristics that usually help agent navigation:

- prioritize `README`, `CLAUDE.md`, package manifests, Docker files, CI files, env examples, route definitions, app bootstrap files, server start files, and shared config
- prioritize top-level exported symbols and public interfaces over private implementation detail
- prioritize likely user-facing boundaries: routes, controllers, handlers, services, stores, reducers, schemas, database models, and tests
- treat large generated/vendor/build folders as noise unless the task explicitly requires them

## Anti-patterns to avoid

Avoid these behaviors:

- reading dozens of files before building a structure map
- using repo-wide grep as the first move in a large unknown codebase
- assuming the framework from one file without confirming through manifests/config
- editing a file before understanding the owning subsystem and adjacent tests
- regenerating the pack repeatedly when nothing structural changed

## Suggested user-facing phrasing when this Skill activates

Use concise status language such as:

- “I’m mapping the repo first so I can target the right subsystem instead of searching blindly.”
- “I found the likely entrypoints and command surface; now I’m narrowing to the files that own this feature.”
- “The context pack is missing, so I’m generating a reusable project map before making changes.”

## If the repo already has strong project memory

If there is a high-quality `CLAUDE.md`, architecture docs, or a maintained project map already checked in, do not duplicate it unnecessarily.

Instead:

- reuse the existing project memory
- generate only the missing context artifacts
- keep `.claude/project-context/` complementary, not redundant

## Validation checklist

Before concluding, verify:

- the pack exists
- the pack points clearly to likely task-relevant folders
- commands are extracted from real config where possible
- entrypoints are plausible
- symbol index is readable and not bloated
- no source files were changed accidentally

## Supporting files

- Builder script: `scripts/build_context_pack.py`
- Installation/usage guide: `README.md`
- Optional example hook snippets: `examples/settings.snippets.jsonc`
