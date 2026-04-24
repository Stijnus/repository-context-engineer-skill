# Repository Context Engineer

Codex guidance for reducing wasteful repo-wide searching. Build and reuse a durable project context pack under `.claude/project-context/` before broad search. The pack is a working repo map, not line-by-line code memory — still read exact files before editing behavior.

## Hard priority rule

**If `.claude/project-context/MANIFEST.json` exists, read the pack BEFORE any file discovery (Read/Glob/Grep, `ls`, `find`, `rg`) and BEFORE asking clarification questions about where code lives.**

The pack tells you which files to read. Searching without consulting it first is the exact waste this flow exists to prevent.

Minimum first reads when a pack exists:
1. `.claude/project-context/OVERVIEW.md`
2. `.claude/project-context/AREAS.md`
3. `.claude/project-context/TASK_ROUTING.md`

Only after those should you do scoped search, and only inside the folders the pack points to.

## When to use

Apply when any are true, even if the user does not name this flow:

- the repository is unfamiliar or spans multiple apps/services/packages
- the task references a feature or subsystem but not exact files
- repeated grep/find/read cycles are getting expensive
- the codebase lacks clear project memory

Do not use for tiny one-file edits when the correct file is already known.

## Trigger phrases

- "Understand this repo before making changes."
- "Build or refresh the repo context pack first."
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

- Write only inside `.claude/project-context/` unless the task requires code changes.
- Never overwrite source files when generating context.
- Do not commit generated artifacts unless the user asks.
- If the builder fails, say so honestly, retry once, then reuse the existing pack only if it still matches the repo.

## Validation

When making code changes, use the repo's documented test, lint, or typecheck commands when clearly available and relevant.

Before concluding, verify:

- the pack exists or the failure was reported honestly
- the pack points clearly to likely task-relevant folders
- commands were extracted from real config where possible
- entrypoints are plausible
- the user-facing summary does not overclaim complete context awareness
- exact file-location answers were verified with query routing, scoped search, or direct reads

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
