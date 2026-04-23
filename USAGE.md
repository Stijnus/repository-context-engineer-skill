# Usage Guide

This guide explains how to use Repository Context Engineer in practice for both **Claude Code** and **Codex**.

## Important first point

There are **no custom slash commands**.

You use this package with normal prompts and, when needed, a normal Python command that builds the project context pack.

## Versions

### V2

Stable baseline:

```bash
python scripts/build_context_pack.py .
```

### V3

Preferred when you want **query-ranked context selection**:

```bash
python scripts/build_context_pack_v3.py .
```

## Updating the installed files

This repo now includes updater scripts for both macOS/Linux and Windows.

### Claude Code on macOS/Linux

If the installed skill is itself a git checkout of this repo:

```bash
bash scripts/update_skill.sh --pull
```

If you want to sync from a different local checkout into the Claude skill install path:

```bash
bash scripts/update_skill.sh --pull --target ~/.claude/skills/repository-context-engineer
```

### Claude Code on Windows

```powershell
powershell -ExecutionPolicy Bypass -File scripts/update_skill.ps1 -Pull
```

or, for a different target path:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/update_skill.ps1 -Pull -Target "$HOME\.claude\skills\repository-context-engineer"
```

### Codex target repository

```bash
bash scripts/update_skill.sh --pull --mode codex --target /path/to/target-repo
```

On Windows:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/update_skill.ps1 -Pull -Mode codex -Target "C:\path\to\target-repo"
```

By default the updater scripts create a backup under:

```text
.repository-context-engineer-backups/
```

inside the target before overwriting managed files.

## What V3 adds

V3 adds several files intended to reduce repeated search and token waste:

- `IMPORT_GRAPH.md`
- `TOKEN_COUNTS.md`
- `TASK_ROUTING.md`
- `CHANGE_HOTSPOTS.md`
- `STALENESS.md`
- `QUERY_CONTEXT.md` when you use `--route-query`
- `QUERY_RESULTS.json` when you use `--route-query`

## Claude Code usage

Claude Code reads `SKILL.md` and uses that as the instruction surface for this package.

Example prompts:

- “Understand this repo before making changes.”
- “Build or refresh the project context pack first.”
- “Map the codebase, then tell me which files likely own onboarding.”
- “Use the repo map first, then scoped search, then direct file reads.”
- “Run V3 query routing for auth and show me the top files first.”

Preferred V3 command for Claude Code:

```bash
python scripts/build_context_pack_v3.py .
```

If the skill is installed project-locally and you still want the older builder:

```bash
python .claude/skills/repository-context-engineer/scripts/build_context_pack.py .
```

## Codex usage

Codex reads `AGENTS.md` and uses that as the repo instruction surface.

Example prompts:

- “Understand this repo before making changes.”
- “Refresh the repo map first, then tell me where billing likely lives.”
- “Map the codebase and identify the likely files for the API auth flow.”
- “Use the repo map first, then scoped search, then direct file reads.”
- “Run V3 query routing for billing and show the ranked files.”

Preferred V3 command for Codex:

```bash
python scripts/build_context_pack_v3.py .
```

## Commands that matter

### Build the V3 pack

```bash
python scripts/build_context_pack_v3.py .
```

### Check whether the pack is stale

```bash
python scripts/build_context_pack_v3.py . --check-stale
```

### Rank likely files for a specific task

```bash
python scripts/build_context_pack_v3.py . --route-query "billing flow"
```

That last command is the important V3 addition.

## What to expect after you use V3

When the package is used correctly, the agent should usually tell you:

1. whether the pack was **generated**, **refreshed**, **reused**, or may be **stale**
2. where the pack was written
3. the top-level ownership map of the repo
4. the key docs, commands, configs, and entrypoints
5. the likely files or folders for your task
6. the confidence boundary: it has a **working repo map**, not full line-by-line memory

### What V3 query routing should additionally tell you

If `--route-query` is used, expect:

1. a ranked list of likely files
2. reasons those files ranked highly
3. import neighbors worth checking next
4. git co-change hints that may reveal adjacent tests/configs
5. token-heavy files that should be postponed until needed

### Example expected reply shape

A good V3-style response might look like:

- “I generated `.claude/project-context/` and ran V3 query routing for `billing flow`.”
- “Top-level ownership looks like: `apps/` for user-facing apps, `packages/` for shared code, `scripts/` for tooling.”
- “The highest-ranked files are `packages/api/src/routes/billing.ts`, `packages/api/src/services/billing_service.ts`, and `apps/web/src/features/billing/*`.”
- “Those ranked highly because of path tokens, symbol matches, and import-graph neighbors.”
- “`packages/api/src/routes/billing.ts` is a good first read; if needed, check its inbound references and co-change partners next.”
- “I have a working repo map, but I still need to read the exact files before editing behavior.”

## What happens next after the pack is built

The correct sequence is:

1. build or reuse the pack
2. read the pack first
3. if the task is specific, run `--route-query`
4. form a file hypothesis
5. run scoped search only in likely folders if still needed
6. read exact files
7. edit code
8. refresh the pack only if structure changed

This is the whole point of the package: **route first, rank second, search third, edit last**.

## Exact-location questions

When you ask things like:

- “Where is onboarding?”
- “Which files own auth?”
- “Where should I change billing?”

You should expect this behavior:

1. the pack is used as the routing layer
2. V3 query routing is used if available
3. the agent narrows to likely folders first
4. scoped search is run only if needed
5. exact files are verified with direct reads

You should **not** expect the agent to claim exact file ownership from the pack alone unless the pack clearly proves it.

## When the pack should be refreshed

Refresh it after structural changes such as:

- adding new apps or services
- renaming important folders
- moving entrypoints
- changing build/test/lint commands
- adding new route groups or feature folders
- changing architecture docs or project conventions

After normal code edits, a stale check is usually enough.

## Failure behavior

If the builder fails, the agent should:

- say the pack was **not** refreshed
- retry once if the failure looks transient
- reuse the existing pack only if it still appears valid
- say the pack may be stale
- continue with query routing or scoped search rather than pretending the repo is fully mapped

## What not to expect

Do not expect this package to:

- provide full line-by-line code understanding
- replace direct file reads before behavior edits
- behave like a compiler or language server
- automatically commit generated `.claude/project-context/` files unless you ask for that

## Quick checklist

Use this package correctly when the agent:

- builds or reuses the pack first
- explains the pack status
- summarizes the repo structure
- ranks likely files for the task when V3 is available
- reads exact files before editing behavior
- avoids broad repo-wide search until it has a routing hypothesis
