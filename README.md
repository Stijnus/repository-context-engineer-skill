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
```

## How to update after changes are pushed to `main`

This repository is currently consumed as normal files, not as a packaged marketplace plugin, so updates from GitHub do **not** arrive automatically unless your install itself is a git checkout that tracks this repo.

### Claude Code: installed as a git checkout

If you cloned this repo directly into the skill directory, update it in place:

```bash
cd ~/.claude/skills/repository-context-engineer
git pull origin main
```

Then restart Claude Code so it reloads the skill files.

### Claude Code: installed by manually copying files

If you copied the files into `~/.claude/skills/repository-context-engineer/`, pull the latest repo somewhere else and copy the updated files over again:

```bash
git clone https://github.com/Stijnus/repository-context-engineer-skill.git /tmp/repository-context-engineer-skill
rm -rf ~/.claude/skills/repository-context-engineer
mkdir -p ~/.claude/skills
cp -R /tmp/repository-context-engineer-skill ~/.claude/skills/repository-context-engineer
```

Then restart Claude Code.

If you already have a local clone, you can replace the first line with:

```bash
cd /path/to/repository-context-engineer-skill
git pull origin main
```

and then copy the refreshed files into `~/.claude/skills/repository-context-engineer/`.

### Codex: installed inside a target repository

If you copied `AGENTS.md` and `scripts/` into a target repo for Codex, update those files from the latest `main` branch and commit them in that target repo:

```bash
cd /path/to/repository-context-engineer-skill
git pull origin main

cp AGENTS.md /path/to/target-repo/AGENTS.md
cp -R scripts /path/to/target-repo/
```

After that, start a new Codex session in the target repo so it sees the updated guidance.

### Recommended update workflow

For the cleanest updates, prefer one of these patterns:

- keep a real git clone in `~/.claude/skills/repository-context-engineer/` and use `git pull origin main`
- or vendor the needed files into each target repo and refresh them when you want to adopt the latest version

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
