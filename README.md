# Repository Context Engineer

A repository-understanding package for **Claude Code and Codex**.

This project is designed for the exact problem you described: agents spending too much time repeatedly searching, grepping, and reading random files because they do not have a durable understanding of the codebase.

## What this package targets

This repo now ships the two instruction surfaces you actually want:

- **Claude Code**: `SKILL.md`
- **Codex**: `AGENTS.md`

Both use the same builder script and the same generated project context pack under:

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

## Output files

The builder generates:

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

## Files in this repo

- `SKILL.md` — Claude Code version
- `AGENTS.md` — Codex version
- `scripts/build_context_pack.py` — shared builder
- `examples/settings.snippets.jsonc` — optional Claude Code hook example

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
```

The included `AGENTS.md` assumes the builder lives at:

```text
scripts/build_context_pack.py
```

If you place it somewhere else, update the command inside `AGENTS.md`.

## Shared workflow

1. Check whether `.claude/project-context/` exists.
2. If missing or stale, run the builder.
3. Read the generated pack first.
4. Route the task to the relevant subsystem.
5. Read only the likely source files.
6. Make changes.
7. Refresh the pack if structure changed.

For exact questions like “where is onboarding?” or “which files own billing?”, use the pack as the routing layer first, then run scoped search in the likely folders. Avoid answering exact ownership from the pack alone unless the generated artifacts already prove it clearly.

After structural edits, such as adding feature folders, moving entrypoints, changing commands, or updating architecture docs, refresh the pack before relying on it for the next task. After ordinary code edits, a stale check is usually enough.

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

## Limitations

- The provided builder uses deterministic heuristics, not a full compiler or language server.
- Symbol extraction is best-effort and intentionally lightweight.
- The pack improves file targeting but does not replace reading exact implementation files before edits.
- For very large enterprise codebases, the best results come from combining this package with existing repo search/index tools.

## Best combination in practice

For the strongest setup:

1. use `CLAUDE.md` for Claude Code project memory when applicable
2. use `SKILL.md` for Claude Code skill packaging
3. use `AGENTS.md` for Codex repo guidance
4. share the same generated `.claude/project-context/` pack across both
5. use native repo search/index tools for precise retrieval

## Good next step

A strong v2 would also:

- read `.gitignore` more precisely
- use Tree-sitter when available
- build area-specific maps per package/app
- track staleness from git changes
- emit task-routing hints based on natural-language intents
- optionally generate a shorter Codex-first `AGENTS.md` map that points into the full pack
