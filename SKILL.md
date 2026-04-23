---
name: repository-context-engineer
description: Build and maintain a persistent project context pack for software repositories. Use when working in a new or large codebase, when a task requires understanding architecture before editing, when file discovery is expensive, or when repeated grep/search/read cycles are likely. Creates reusable structure, commands, entrypoints, area maps, symbol indexes, and query-ranked file selection so future tasks can target the correct files faster.
allowed-tools: Read, Write, Edit, MultiEdit, Bash, Glob, Grep, LS
---

# Repository Context Engineer

This Skill exists to reduce wasteful repo-wide searching and improve code changes by giving Claude a durable, navigable understanding of the repository before implementation starts.

The goal is **not** to dump the whole repo into context. The goal is to create and maintain a **project context pack** under `.claude/project-context/` that acts as reusable operating knowledge for future tasks.

## Context boundary

This Skill gives a **working repo map**, not complete code memory.

After using it, you should know:

- the top-level folders and likely ownership boundaries
- the key docs, commands, configs, entrypoints, and golden files
- the likely files or folders for a feature, route, service, or subsystem
- the project conventions that should guide edits

Do not claim full line-by-line understanding of the repo. Before editing behavior, read the exact files you will change and any adjacent tests/configs.

## How users trigger this Skill

There are no custom slash commands.

Users trigger this Skill with ordinary prompts such as:

- “Understand this repo before making changes.”
- “Build or refresh the project context pack first.”
- “Map the codebase, then tell me which files likely own billing.”
- “Use the repo map first, then scoped search, then direct file reads.”
- “Run V3 query routing for auth and tell me the top files first.”

If the task clearly requires repo understanding before editing, activate this Skill even if the user does not name it explicitly.

## Preferred builder

If `scripts/build_context_pack_v3.py` exists, prefer it over the older builder.

Preferred commands:

```bash
python scripts/build_context_pack_v3.py .
python scripts/build_context_pack_v3.py . --check-stale
python scripts/build_context_pack_v3.py . --route-query "billing flow"
```

Fallback only if V3 is unavailable:

```bash
python .claude/skills/repository-context-engineer/scripts/build_context_pack.py .
```

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

## Required user-facing output after building or refreshing

After building or refreshing the pack, summarize:

- where the pack was written
- whether it was generated, refreshed, reused, or stale
- the top-level folder ownership map
- the key docs and golden files
- likely files for the current task, if a task is known
- the confidence boundary: "working repo map, exact files still need to be read before editing"

If V3 query routing is used, also summarize:

- the top ranked files for the query
- why they ranked highly
- which import neighbors or co-change partners should be checked next
- whether any token-heavy files should be delayed until later

## Core operating rule

Before broad searching, check whether `.claude/project-context/` already exists and is still likely usable.

Start by reading only these files if present:

- `.claude/project-context/OVERVIEW.md`
- `.claude/project-context/STACK.md`
- `.claude/project-context/COMMANDS.md`
- `.claude/project-context/ENTRYPOINTS.md`
- `.claude/project-context/AREAS.md`
- `.claude/project-context/SYMBOL_INDEX.md`
- `.claude/project-context/TASK_ROUTING.md`
- `.claude/project-context/TOKEN_COUNTS.md`
- `.claude/project-context/IMPORT_GRAPH.md`

Only expand into raw source files after these artifacts narrow the likely target area.

## Workflow

### 1. Decide whether the context pack is missing or stale

Treat the context pack as **missing or stale** when:

- `.claude/project-context/` does not exist.
- The repository structure appears to have changed significantly.
- The task is in a subsystem that is absent from the pack.
- The pack predates a large refactor or newly added app/service.

Prefer `--check-stale` when V3 is available.

### 2. Build or refresh the context pack

Use the preferred V3 builder when available.

### 3. Read the pack in layers

Read in this order unless the task clearly needs something else:

1. `OVERVIEW.md`
2. `STACK.md`
3. `COMMANDS.md`
4. `ENTRYPOINTS.md`
5. `AREAS.md`
6. `SYMBOL_INDEX.md`
7. `TASK_ROUTING.md`
8. `TOKEN_COUNTS.md`
9. `IMPORT_GRAPH.md`
10. `CHANGE_HOTSPOTS.md`
11. `DIRECTORY_TREE.txt`
12. `IMPORTANT_FILES.md`

Do not load everything at once if not needed.

### 4. Route the task before reading code

After reading the pack, identify:

- likely subsystem
- likely owning folder(s)
- likely entrypoints
- likely tests
- likely configuration files

If the task is specific enough, run V3 query routing first:

```bash
python scripts/build_context_pack_v3.py . --route-query "<task or feature>"
```

Then do targeted reads/searches only in those areas.

### 5. Answer exact location questions with scoped lookup

When the user asks "where is X?", "which files own X?", or "where should we change X?":

1. Use the pack to identify likely folders, routes, entrypoints, and symbols.
2. If available, run `--route-query` for the exact task phrase.
3. Search only the likely folders first.
4. Expand search only if the first pass is weak or contradictory.
5. State whether the answer came from the context pack, query routing, scoped search, or direct file reads.

Do not imply the pack alone proves exact ownership. Treat it as the routing layer, then verify exact files with targeted search or reads.

### 6. State the file hypothesis before editing

Before making code changes, explicitly form a short working hypothesis:

- which files likely need changes
- why those files were selected
- what nearby tests/configs may also need updates

If the hypothesis is weak, improve it with query routing and targeted reads rather than broad repo scans.

### 7. Update the context pack after changes

Re-run the builder after:

- adding new apps/services/packages
- renaming important folders
- moving entrypoints
- adding major commands/scripts
- adding new route groups or API surfaces
- adding, deleting, or moving feature folders
- changing architecture docs or project conventions

After normal code edits that do not change structure, do not rebuild automatically unless the next task depends on an updated map.

### 8. Handle builder failures honestly

If the builder fails:

- Do not say the pack was refreshed.
- Retry once if the failure looks transient.
- If retry still fails, read the existing pack only if it exists and clearly matches the current repo.
- Tell the user the pack may be stale and continue with scoped search inside likely folders.

## Editing constraints

- Never overwrite source files when generating context.
- Only write inside `.claude/project-context/` unless the user asked for code changes.
- Keep the pack concise and navigable.
- Prefer deterministic extraction over speculative summaries.
- If a signal is uncertain, label it as probable rather than authoritative.
- Do not commit generated context artifacts unless the user explicitly wants them checked in.

## Anti-patterns to avoid

Avoid these behaviors:

- reading dozens of files before building a structure map
- using repo-wide grep as the first move in a large unknown codebase
- assuming the framework from one file without confirming through manifests/config
- editing a file before understanding the owning subsystem and adjacent tests
- regenerating the pack repeatedly when nothing structural changed
- telling the user you have complete repo awareness after only building the pack
- answering exact ownership questions from the pack alone when a scoped search is needed
- ignoring the query-ranked file list when V3 is available

## Validation checklist

Before concluding, verify:

- the pack exists
- commands are extracted from real config where possible
- entrypoints are plausible
- symbol index is readable and not bloated
- user-facing summary does not overclaim complete context awareness
- exact file-location answers were verified with query routing, scoped search, or direct reads when needed

## Supporting files

- Stable builder: `scripts/build_context_pack.py`
- V3 builder: `scripts/build_context_pack_v3.py`
- Installation/usage guide: `README.md`
- Practical examples and commands: `USAGE.md`
- Optional example hook snippets: `examples/settings.snippets.jsonc`
