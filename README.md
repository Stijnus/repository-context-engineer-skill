# Repository Context Engineer Skill

A Claude Code Skill for **persistent repository understanding**.

This Skill is designed for the exact problem you described: agents spending too much time repeatedly searching, grepping, and reading random files because they do not have a durable understanding of the codebase.

## What problem this solves

Most current approaches improve only one part of the problem:

- **Repo packers** like Repomix, GitIngest, and Code2Prompt are useful for one-shot prompt creation.
- **Indexers/retrievers** like Cursor and Sourcegraph improve search and retrieval.
- **Claude Code memory** (`CLAUDE.md`, auto-memory, subagents) helps with instructions and recurring knowledge.

But those do not fully solve the missing middle layer:

> a reusable, project-specific operating model that tells the agent what the repo is, how it is organized, where execution starts, which commands matter, and which folders own which responsibilities.

This Skill adds that middle layer by generating a **project context pack** inside the repository.

## Core idea

Instead of making the model rediscover the codebase on every task, generate and maintain lightweight project knowledge under:

```text
.claude/project-context/
```

That folder becomes a reusable navigation layer for future tasks.

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
- `MANIFEST.json`

## Install

### Project-local install

Create this folder structure in your repository:

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

### Personal install

Put the same folder under:

```text
~/.claude/skills/repository-context-engineer/
```

Then adjust the script path in `SKILL.md` if you want the skill to write into the current project from a global install.

## Use

Ask Claude Code to work in a repo as normal. The Skill should trigger automatically when the task suggests that repo understanding is required.

Examples:

- “Find where auth is implemented and add refresh token support.”
- “This monorepo is messy; understand it first and then fix the billing flow.”
- “Before changing anything, map the repo and tell me which files own the API layer.”
- “Stop searching blindly and build project context first.”

## Suggested workflow

1. Check for `.claude/project-context/`
2. If missing/stale, run the builder
3. Read the generated pack first
4. Route the task to the relevant subsystem
5. Read only the likely source files
6. Make changes
7. Refresh the pack if structure changed

## Why this is different from repo packers

Repo packers are usually **snapshot exporters**. They are excellent for sending a repo into an LLM once.

This Skill is instead a **persistent repo operating layer**:

- smaller than a full repo dump
- cheaper to load repeatedly
- targeted to agent navigation
- durable across tasks
- easy to keep up to date

## Why this is different from semantic indexing alone

Embeddings and semantic search help find relevant files, but they do not inherently explain:

- the startup path of the app
- which commands are canonical
- which top-level folders correspond to which responsibilities
- which files deserve to be read first
- which symbols form the public surface area of the project

This Skill makes those things explicit.

## Limitations

- The provided builder uses deterministic heuristics, not a full compiler or language server.
- Symbol extraction is best-effort and intentionally lightweight.
- For very large enterprise codebases, the best results come from combining this Skill with existing repo search/index tools.

## Best combination in practice

For the strongest setup, combine:

1. `CLAUDE.md` for project conventions and workflow
2. this Skill for durable repo structure understanding
3. native search/index tools for precise retrieval
4. optional subagents for specialized tasks

## Good next step

If you want, the next iteration should be a **v2 hybrid skill** that also:

- reads `.gitignore` more precisely
- uses Tree-sitter when available
- builds area-specific maps per package/app
- tracks staleness from git changes
- emits task-routing hints based on natural-language intents
