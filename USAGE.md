# Usage Guide

This guide explains how to use Repository Context Engineer in practice for both **Claude Code** and **Codex**.

## Important first point

There are **no custom slash commands**.

You use this package with normal prompts and, when needed, a normal Python command that builds the project context pack.

## What this package actually does

It builds a reusable repo map under:

```text
.claude/project-context/
```

That repo map helps the agent understand:

- the project structure
- likely subsystem boundaries
- likely entrypoints
- important commands
- important files
- likely files for the task you asked for

It does **not** replace reading exact implementation files before editing behavior.

---

## Claude Code usage

### How Claude Code uses it

Claude Code reads `SKILL.md` and uses that as the instruction surface for this package.

In practice, that means you normally just ask Claude to work in the repo. If the task requires repo understanding first, the skill should kick in.

### Example prompts for Claude Code

Use prompts like these:

- “Understand this repo before making changes.”
- “Build or refresh the project context pack first.”
- “Map the codebase, then tell me which files likely own onboarding.”
- “Use the repo map first, then scoped search, then direct file reads.”
- “Before editing auth, tell me the entrypoints, key configs, and likely owning files.”

### Manual builder command for Claude Code

If the skill is installed project-locally:

```bash
python .claude/skills/repository-context-engineer/scripts/build_context_pack.py .
```

If the skill is installed globally, adapt the path and run:

```bash
python /path/to/repository-context-engineer/scripts/build_context_pack.py .
```

---

## Codex usage

### How Codex uses it

Codex reads `AGENTS.md` and uses that as the repo instruction surface.

In practice, this means the repo itself tells Codex to build or reuse the context pack before broad searching when the task requires repo understanding.

### Example prompts for Codex

Use prompts like these:

- “Understand this repo before making changes.”
- “Refresh the repo map first, then tell me where billing likely lives.”
- “Map the codebase and identify the likely files for the API auth flow.”
- “Use the repo map first, then scoped search, then direct file reads.”

### Manual builder command for Codex

If the repo contains the builder at `scripts/build_context_pack.py`, run:

```bash
python scripts/build_context_pack.py .
```

---

## What commands matter

There are two kinds of commands here.

### 1. User prompts

These are natural-language prompts that trigger the behavior:

- “Understand this repo before making changes.”
- “Build or refresh the context pack first.”
- “Map the codebase before you search broadly.”
- “Tell me which files likely own payments, then verify with scoped search.”

### 2. Builder commands

These commands generate the context pack:

**Claude Code project-local install**

```bash
python .claude/skills/repository-context-engineer/scripts/build_context_pack.py .
```

**Codex / generic layout**

```bash
python scripts/build_context_pack.py .
```

---

## What to expect after you use it

When the package is used correctly, the agent should usually tell you something like this:

1. whether the pack was **generated**, **refreshed**, **reused**, or may be **stale**
2. where the pack was written
3. the top-level ownership map of the repo
4. the key docs, commands, configs, and entrypoints
5. the likely files or folders for your task
6. the confidence boundary: it has a **working repo map**, not full line-by-line memory

### Example expected reply shape

A good response after activation might look like:

- “I generated `.claude/project-context/` and mapped the repo.”
- “Top-level ownership looks like: `apps/` for user-facing apps, `packages/` for shared code, `scripts/` for tooling.”
- “Key entrypoints and configs appear to be `apps/web/src/main.tsx`, `packages/api/src/server.ts`, and `package.json` scripts.”
- “For your billing task, the likely files are `packages/api/src/routes/billing.ts` and `apps/web/src/features/billing/*`.”
- “I have a working repo map, but I still need to read the exact files before editing behavior.”

---

## What happens next after the pack is built

The correct sequence is:

1. build or reuse the pack
2. read the pack first
3. form a file hypothesis
4. run scoped search only in likely folders
5. read exact files
6. edit code
7. refresh the pack only if structure changed

This is the whole point of the package: **route first, search second, edit last**.

---

## Exact-location questions

When you ask things like:

- “Where is onboarding?”
- “Which files own auth?”
- “Where should I change billing?”

You should expect this behavior:

1. the pack is used as the routing layer
2. the agent narrows to likely folders first
3. scoped search is run in those folders
4. exact files are verified with direct reads

You should **not** expect the agent to claim exact file ownership from the pack alone unless the pack clearly proves it.

---

## When the pack should be refreshed

Refresh it after structural changes such as:

- adding new apps or services
- renaming important folders
- moving entrypoints
- changing build/test/lint commands
- adding new route groups or feature folders
- changing architecture docs or project conventions

After normal code edits, a stale check is usually enough.

---

## Failure behavior

If the builder fails, the agent should:

- say the pack was **not** refreshed
- retry once if the failure looks transient
- reuse the existing pack only if it still appears valid
- say the pack may be stale
- continue with scoped search rather than pretending the repo is fully mapped

---

## What not to expect

Do not expect this package to:

- provide full line-by-line code understanding
- replace direct file reads before behavior edits
- behave like a compiler or language server
- automatically commit generated `.claude/project-context/` files unless you ask for that

---

## Quick checklist

Use this package correctly when the agent:

- builds or reuses the pack first
- explains the pack status
- summarizes the repo structure
- identifies likely files for the task
- reads exact files before editing behavior
- avoids broad repo-wide search until it has a routing hypothesis
