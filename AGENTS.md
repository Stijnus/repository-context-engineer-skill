# Repository Context Engineer

Use this repository guidance when Codex is working in an unfamiliar or non-trivial codebase and the task does not already name the exact files to change.

## Purpose

Build or reuse a **working repo map** before broad searching.

The goal is not full line-by-line code memory. The goal is to create a durable navigation layer under:

```text
.claude/project-context/
```

This pack should help answer:

- what kind of project this is
- how the repo is structured
- which files are likely entrypoints and key configs
- which commands matter for build, test, lint, and run
- which top-level folders own which responsibilities
- which files are likely relevant to the current task

## How this is triggered

There are no custom slash commands.

Use this flow when the user says things like:

- “Understand this repo before making changes.”
- “Build or refresh the repo context pack first.”
- “Map the codebase, then tell me which files likely own auth.”
- “Use the repo map first, then scoped search, then direct file reads.”

If a task clearly requires repo understanding before editing, apply this flow even if the user does not name it explicitly.

## When to use this

Use this flow when any of the following are true:

- the repository is unfamiliar
- the task references a feature or subsystem but not exact files
- repeated grep/find/read cycles are getting expensive
- the task spans multiple folders, packages, services, or apps
- you need a better file hypothesis before editing

Do not use this flow for tiny one-file edits when the correct file is already known.

## Core workflow

### 1. Check for an existing context pack

Look for:

- `.claude/project-context/OVERVIEW.md`
- `.claude/project-context/STACK.md`
- `.claude/project-context/COMMANDS.md`
- `.claude/project-context/ENTRYPOINTS.md`
- `.claude/project-context/AREAS.md`
- `.claude/project-context/SYMBOL_INDEX.md`

If the pack exists and still appears usable, read it first before broad search.

### 2. Build or refresh the pack if needed

From the repository root, run:

```bash
python scripts/build_context_pack.py .
```

Use the generated pack as the routing layer for the rest of the task.

Treat the pack as missing or stale when:

- `.claude/project-context/` does not exist
- the repository structure changed significantly
- the needed subsystem is missing from the pack
- the pack predates a major refactor or a new app/service/package

### 3. Read the pack in layers

Default order:

1. `OVERVIEW.md`
2. `STACK.md`
3. `COMMANDS.md`
4. `ENTRYPOINTS.md`
5. `AREAS.md`
6. `SYMBOL_INDEX.md`
7. `DIRECTORY_TREE.txt`
8. `IMPORTANT_FILES.md`

Do not load everything at once unless the task really needs it.

### 4. Route the task before reading code

After reading the pack, identify:

- likely subsystem
- likely owning folder(s)
- likely entrypoints
- likely tests
- likely configuration files

Then do targeted reads and scoped searches only in those areas.

### 5. Answer exact location questions with scoped lookup

When the user asks:

- where is X?
- which files own X?
- where should we change X?

Use this order:

1. use the pack to identify likely folders, entrypoints, and symbols
2. search only those likely folders first
3. expand search only if the first pass is weak or contradictory
4. say whether the answer came from the pack, scoped search, or direct file reads

Do not imply the pack alone proves exact ownership. Treat it as the routing layer, then verify exact files with scoped search or direct reads.

### 6. Read exact files before editing behavior

Before code changes, form a short file hypothesis:

- which files likely need changes
- why those files were selected
- what adjacent tests/configs may need updates

Then read the exact implementation files before editing.

A built pack means you have a **working repo map**, not complete code memory.

### 7. Refresh after structural changes

Rebuild the pack after changes such as:

- adding new apps/services/packages
- renaming important folders
- moving entrypoints
- adding major commands/scripts
- adding new route groups or API surfaces
- adding, deleting, or moving feature folders
- changing architecture docs or project conventions

After normal code edits, do not rebuild automatically unless the next task depends on an updated map.

### 8. Handle builder failures honestly

If the builder fails:

- do not say the pack was refreshed
- retry once if the failure looks transient
- if retry still fails, use the existing pack only if it clearly still matches the repo
- tell the user the pack may be stale
- continue with scoped search inside likely folders

## Expected user-visible output

After building, refreshing, or reusing the pack, report:

- whether the pack was generated, refreshed, reused, or may be stale
- where the pack was written
- the top-level ownership map
- the key docs, commands, configs, and entrypoints
- the likely files or folders for the current task, if one is known
- the confidence boundary: working repo map, exact files still need to be read before editing

## Editing constraints

- Never overwrite source files when generating context.
- Only write inside `.claude/project-context/` unless the task requires code changes.
- Prefer deterministic extraction over speculative summaries.
- If a signal is uncertain, label it as probable rather than authoritative.
- Do not commit generated context artifacts unless the user explicitly asks for them.

## Validation

When you make code changes, use the repo's documented test, lint, or typecheck commands when they are clearly available and relevant.

Before concluding, verify:

- the pack exists or failure was reported honestly
- the pack points clearly to likely task-relevant folders
- commands were extracted from real config where possible
- entrypoints are plausible
- the user-facing summary does not overclaim complete context awareness
- exact file-location answers were verified with scoped search or direct reads when needed
