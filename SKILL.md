---
name: repository-context-engineer
description: Use when working in an unfamiliar or large repository, when a task requires understanding architecture before editing, when file discovery keeps failing, or when the agent is about to run repeated grep/search/read cycles looking for ownership of a feature, route, service, or subsystem.
allowed-tools: Read, Write, Edit, MultiEdit, Bash, Glob, Grep, LS
---

# Repository Context Engineer

Reduce wasteful repo-wide searching by building and reusing a durable project context pack under `.claude/project-context/`. The pack is a working repo map, not line-by-line code memory — still read exact files before editing behavior.

## When to use

Apply when any are true, even if the user does not name the Skill:

- the repository is unfamiliar or spans multiple apps/services/packages
- the task references a feature or subsystem but not exact files
- repeated grep/find/read cycles are getting expensive
- the codebase lacks clear `CLAUDE.md` project memory

Do not use for tiny one-file edits when the correct file is already known.

## Trigger phrases

- "Understand this repo before making changes."
- "Build or refresh the project context pack first."
- "Map the codebase, then tell me which files likely own `<X>`."
- "Use the repo map first, then scoped search, then direct file reads."
- "Run V3 query routing for `<X>` and tell me the top files first."

## Decision flow

1. Is `.claude/project-context/` present?
   - No → build the pack.
   - Yes → run `--check-stale`. If STALE or the needed subsystem is missing, refresh. Otherwise reuse.
2. Does `scripts/build_context_pack_v3.py` exist?
   - Yes → prefer V3 for build, stale-check, and `--route-query`.
   - No → fall back to V2 (`scripts/build_context_pack.py`).
3. Does `MANIFEST.json` show `builder_version` starting with `2.` while V3 is available? → refresh with V3.

Treat the pack as stale when repo structure changed, a new app/service/package appeared, or the current task is in a subsystem absent from the pack.

## Quick reference

| Goal | Command |
|---|---|
| Build (V3, preferred) | `python scripts/build_context_pack_v3.py .` |
| Stale check | `python scripts/build_context_pack_v3.py . --check-stale` |
| Rank files for a task | `python scripts/build_context_pack_v3.py . --route-query "<task>"` |
| Fallback build (V2) | `python scripts/build_context_pack.py .` |

## Layered read order

Read pack files on demand, not all at once:

1. `OVERVIEW.md`, `STACK.md`, `COMMANDS.md`
2. `ENTRYPOINTS.md`, `AREAS.md`
3. `SYMBOL_INDEX.md`, `TASK_ROUTING.md`
4. `TOKEN_COUNTS.md`, `IMPORT_GRAPH.md`, `CHANGE_HOTSPOTS.md`
5. `DIRECTORY_TREE.txt`, `IMPORTANT_FILES.md`

If `--route-query` was run, also read `QUERY_CONTEXT.md` and prefer its ranked files over broad search.

## Exact-location questions

For "where is X?", "which files own X?", "where should I change X?":

1. Use the pack to narrow to likely folders, entrypoints, symbols.
2. Run `--route-query "<exact task phrase>"` when V3 is available.
3. Search only those folders first; expand only if the first pass is weak.
4. Verify with direct reads before editing behavior.
5. State which layer produced the answer: pack, routing, scoped search, or direct read.

Do not imply the pack alone proves exact ownership.

## Output contract

After building, refreshing, or reusing the pack, report:

- pack status: generated / refreshed / reused / stale / failed
- where it was written
- top-level ownership map
- key docs, commands, entrypoints
- likely files for the current task, if any
- confidence boundary: working map, exact files still need to be read

If `--route-query` was used, also report ranked files, why they ranked, import/co-change neighbors worth checking, and token-heavy files to delay.

## Refresh triggers

Rebuild after structural changes: new apps/services/packages, renamed important folders, moved entrypoints, new route groups or API surfaces, added/removed feature folders, changed architecture docs. After normal code edits, prefer `--check-stale` over an unconditional rebuild.

## Editing constraints

- Write only inside `.claude/project-context/` unless the user asked for code changes.
- Never overwrite source files when generating context.
- Do not commit generated artifacts unless the user asks.
- If the builder fails, say so honestly, retry once, then reuse the existing pack only if it still matches the repo.

## Anti-patterns

- repo-wide grep as the first move
- reading dozens of files before building a map
- regenerating the pack after trivial edits
- claiming complete repo awareness after only building the pack
- ignoring the V3 query-ranked list when it exists

## Supporting files

- `scripts/build_context_pack_v3.py` — preferred builder with routing, graphs, token counts
- `scripts/build_context_pack.py` — stable V2 baseline
- `USAGE.md` — commands, examples, expected output shape, failure behavior
- `README.md` — install/update, target paths, backup behavior
- `examples/settings.snippets.jsonc` — optional hook samples
