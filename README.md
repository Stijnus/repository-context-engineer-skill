# Repository Context Engineer

A repository-understanding package for **Claude Code and Codex**.

This project is designed for the exact problem you described: agents spending too much time repeatedly searching, grepping, and reading random files because they do not have a durable understanding of the codebase.

## What this package targets

This repo now ships the two instruction surfaces you actually want:

- **Claude Code**: `SKILL.md`
- **Codex**: `AGENTS.md`

Both use the same generated project context pack under:

```text
.claude/project-context/
```

That means Claude Code and Codex can share the same durable repo map instead of rediscovering the project from scratch on every task.

## What problem this solves

Most current approaches improve only one part of the problem:

- **Repo packers** like Repomix, GitIngest, and Code2Prompt are useful for one-shot prompt creation.
- **Indexers/retrievers** like Cursor and Sourcegraph improve search and retrieval.
- **Claude Code memory** (`CLAUDE.md`, auto-memory, subagents) helps with instructions and recurring knowledge.
- **Codex repo guidance** through `AGENTS.md` helps with navigation, commands, and project conventions.

But those do not fully solve the missing middle layer:

> a reusable, project-specific operating model that tells the agent what the repo is, how it is organized, where execution starts, which commands matter, and which folders own which responsibilities.

This package adds that middle layer by generating a **project context pack** inside the repository.

## Core idea

Instead of making the model rediscover the codebase on every task, generate and maintain lightweight project knowledge under:

```text
.claude/project-context/
```

That folder becomes a reusable navigation layer for future tasks.

## What the context pack is and is not

The pack gives the agent a **working repo map**:

- folder ownership and likely subsystem boundaries
- key docs, commands, configs, entrypoints, and important files
- likely files for a feature, route, service, or domain concept

It is not full line-by-line code understanding. The agent should still read exact files before editing behavior, and should say when an answer came from the pack, scoped search, or direct file reads.

## Files in this repo

- `SKILL.md` — Claude Code version
- `AGENTS.md` — Codex version
- `scripts/build_context_pack.py` — stable V2 builder
- `scripts/build_context_pack_v3.py` — V3 graph-ranked builder
- `scripts/update_skill.sh` — macOS/Linux updater for Claude installs and Codex-target sync
- `scripts/update_skill.ps1` — Windows updater for Claude installs and Codex-target sync
- `examples/settings.snippets.jsonc` — optional Claude Code hook example
- `USAGE.md` — practical examples, commands, and expected output

## Recommended versions

### V2

Use V2 if you want the simpler, stable builder:

```bash
python scripts/build_context_pack.py .
```

### V3

Use V3 if you want **query-ranked context selection** and lower search churn:

```bash
python scripts/build_context_pack_v3.py .
```

V3 adds:

- `IMPORT_GRAPH.md`
- `TOKEN_COUNTS.md`
- `TASK_ROUTING.md`
- `CHANGE_HOTSPOTS.md`
- `STALENESS.md`
- optional `QUERY_CONTEXT.md`
- optional `QUERY_RESULTS.json`

## Preferred V3 commands

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

That last command is the important V3 addition. It writes a ranked file list for the query into:

- `.claude/project-context/QUERY_CONTEXT.md`
- `.claude/project-context/QUERY_RESULTS.json`

## Critical: install the pack-awareness hook

The skill's files being on disk is **not enough** for Claude to actually use the pack. You also need a single global hook that tells Claude a pack exists. Without this hook Claude often ignores the pack and grep-bombs anyway.

Add this to `~/.claude/settings.json` (global, one time):

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "test -f .claude/project-context/MANIFEST.json && echo 'REPO MAP AVAILABLE at .claude/project-context/. READ these files before any Read/Glob/Grep: OVERVIEW.md, AREAS.md, TASK_ROUTING.md. The pack already exists — do NOT rebuild it. The pack already ranks files for common tasks; consult it to pick the right source files, then read those exact files.' || true"
          }
        ]
      }
    ]
  }
}
```

How it behaves:

- Fires once per prompt.
- If the current repo has `.claude/project-context/MANIFEST.json`, injects a one-line reminder for Claude.
- If the repo has no pack, the hook is a silent no-op (zero overhead).
- Install once, works in every repo you later build a pack in.

This is the single most important install. The copy in [`examples/settings.snippets.jsonc`](examples/settings.snippets.jsonc) includes both this hook and the optional auto-rebuild hook.

## Install for Claude Code

Install into a project like this:

```text
.claude/
  skills/
    repository-context-engineer/
      SKILL.md
      README.md
      scripts/
        build_context_pack.py
        build_context_pack_v3.py
        update_skill.sh
        update_skill.ps1
      examples/
        settings.snippets.jsonc
```

Then restart Claude Code.

You can also install it globally under:

```text
~/.claude/skills/repository-context-engineer/
```

If you do that, adjust the script path in `SKILL.md` if needed.

## Install for Codex

Codex reads `AGENTS.md`, so place these files in the target repository:

```text
AGENTS.md
scripts/
  build_context_pack.py
  build_context_pack_v3.py
  update_skill.sh
  update_skill.ps1
```

## How to update after changes are pushed to `main`

This repository now includes updater scripts for both macOS/Linux and Windows.

They can do two things:

- pull the latest changes from `origin/main` in a local checkout
- sync the managed files into either a Claude Code skill install or a Codex target repository

By default the scripts create a file-level backup under:

```text
.repository-context-engineer-backups/
```

inside the target before overwriting managed files.

### Claude Code on macOS/Linux

If your installed skill directory is itself a git checkout of this repo, run:

```bash
bash scripts/update_skill.sh --pull
```

If you want to update a different Claude skill install from another local clone of this repo, run:

```bash
bash scripts/update_skill.sh --pull --target ~/.claude/skills/repository-context-engineer
```

### Claude Code on Windows

If your installed skill directory is itself a git checkout of this repo, run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/update_skill.ps1 -Pull
```

If you want to update a different Claude skill install from another local clone of this repo, run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/update_skill.ps1 -Pull -Target "$HOME\.claude\skills\repository-context-engineer"
```

### Codex target repository

To refresh the vendored Codex files in a target repository from a local checkout of this repo:

```bash
bash scripts/update_skill.sh --pull --mode codex --target /path/to/target-repo
```

On Windows:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/update_skill.ps1 -Pull -Mode codex -Target "C:\path\to\target-repo"
```

That updates only the managed Codex files:

- `AGENTS.md`
- `scripts/build_context_pack.py`
- `scripts/build_context_pack_v3.py`
- `scripts/update_skill.sh`
- `scripts/update_skill.ps1`

### Manual fallback

You can still update manually with `git pull` and file copies, but the updater scripts are now the recommended path.

After any update, restart Claude Code or start a new Codex session so the new instructions are loaded.

## How to use it in practice

### There are no special slash commands

This package does **not** add custom slash commands.

Use normal prompts such as:

- “Understand this repo before making changes.”
- “Build or refresh the repo context pack first.”
- “Map the codebase, then tell me which files likely own auth.”
- “Use the repo map first, then scoped search, then direct file reads.”
- “Run V3 query routing for billing and tell me the top files first.”

For Claude Code, `SKILL.md` tells Claude when to apply this flow.

For Codex, `AGENTS.md` tells Codex when to apply this flow.

## What to expect from the agent

After the package is used correctly, the agent should usually tell you:

- whether the context pack was **generated**, **refreshed**, **reused**, or is likely **stale**
- where the pack was written
- the top-level ownership map of the repo
- the key docs, commands, configs, and entrypoints
- the most likely files or folders for your task
- the confidence boundary: it has a **working repo map**, not full line-by-line memory

With V3 query routing, the agent should also be able to tell you:

- which files were ranked highest for the query
- why those files ranked highly
- which import neighbors or co-change partners should be checked next
- which heavy files should be delayed because they cost too many tokens

## What not to expect

Do not expect this package to:

- instantly know exact file ownership without verification
- replace direct file reads before behavior edits
- behave like a full language server or compiler
- automatically commit generated `.claude/project-context/` output unless you explicitly want that

## Why this is different from repo packers

Repo packers are usually **snapshot exporters**. They are excellent for sending a repo into an LLM once.

This package is instead a **persistent repo operating layer**:

- smaller than a full repo dump
- cheaper to load repeatedly
- targeted to agent navigation
- durable across tasks
- easy to keep up to date
- reusable by both Claude Code and Codex

## Why this is different from semantic indexing alone

Embeddings and semantic search help find relevant files, but they do not inherently explain:

- the startup path of the app
- which commands are canonical
- which top-level folders correspond to which responsibilities
- which files deserve to be read first
- which symbols form the public surface area of the project

This package makes those things explicit.

## V3 design goal

V3 is the first version that moves beyond a static repo map and toward **task-specific context concentration**.

The idea is:

1. keep a reusable global repo map
2. build graph and hotspot signals once
3. route the current query to the smallest high-signal file set
4. read exact files only after ranking them

That is the practical path to reducing repeated search loops and token waste.
