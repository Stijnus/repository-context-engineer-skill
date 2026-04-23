#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

DEFAULT_IGNORE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".next",
    ".nuxt",
    ".turbo",
    ".vercel",
    ".idea",
    ".vscode",
    "node_modules",
    "dist",
    "build",
    "coverage",
    "vendor",
    "tmp",
    "temp",
    "out",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".pnpm-store",
    ".yarn",
    ".cache",
    ".expo",
    ".gradle",
    "Pods",
    "DerivedData",
    "__pycache__",
    ".claude/project-context",
}

TEXT_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".json", ".jsonc", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".conf", ".md", ".txt", ".sh", ".bash", ".zsh", ".go", ".rs", ".java",
    ".kt", ".kts", ".php", ".rb", ".cs", ".cpp", ".cc", ".cxx", ".c", ".h", ".hpp", ".swift",
    ".sql", ".graphql", ".gql", ".env", ".example", ".xml", ".html", ".css", ".scss", ".sass",
    ".less", ".vue", ".svelte", ".dart", ".lock", ".gitignore", ".dockerignore",
}

IMPORTANT_FILE_PATTERNS = [
    "README.md", "CLAUDE.md", "package.json", "pnpm-workspace.yaml", "turbo.json", "nx.json",
    "pyproject.toml", "requirements.txt", "Pipfile", "poetry.lock", "Cargo.toml", "go.mod",
    "composer.json", "Gemfile", "pom.xml", "build.gradle", "settings.gradle", "Makefile",
    "Dockerfile", "docker-compose.yml", "docker-compose.yaml", ".env.example", ".env.sample",
    "next.config.js", "next.config.mjs", "next.config.ts", "vite.config.ts", "vite.config.js",
    "tsconfig.json", "jest.config.js", "jest.config.ts", "playwright.config.ts", "cypress.config.ts",
    "app.py", "main.py", "server.py", "manage.py", "main.go", "src/main.ts", "src/index.ts", "src/App.tsx",
]

ENTRYPOINT_NAME_HINTS = [
    "main", "index", "app", "server", "cli", "manage", "program", "routes", "router", "api", "worker"
]

MAX_TEXT_FILE_BYTES = 350_000
MAX_SYMBOLS_PER_FILE = 40
MAX_TREE_LINES = 500
MAX_IMPORTANT_FILES = 80


@dataclass
class FileInfo:
    path: str
    ext: str
    size: int
    top_level: str


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def is_probably_text(path: Path) -> bool:
    if path.suffix.lower() in TEXT_EXTENSIONS:
        return True
    name = path.name.lower()
    return name in {"dockerfile", "makefile", ".env", ".env.example", ".env.sample", ".gitignore"}


def load_text(path: Path) -> str | None:
    try:
        if path.stat().st_size > MAX_TEXT_FILE_BYTES:
            return None
        raw = path.read_bytes()
        if b"\x00" in raw:
            return None
        return raw.decode("utf-8", errors="ignore")
    except Exception:
        return None


def walk_files(root: Path) -> list[FileInfo]:
    results: list[FileInfo] = []
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root)
        parts = [] if rel_dir == "." else rel_dir.split(os.sep)
        dirnames[:] = [d for d in dirnames if d not in DEFAULT_IGNORE_DIRS and not d.startswith(".DS_")]
        if any(part in DEFAULT_IGNORE_DIRS for part in parts):
            dirnames[:] = []
            continue

        for filename in filenames:
            path = Path(dirpath) / filename
            rel = path.relative_to(root).as_posix()
            if any(seg in DEFAULT_IGNORE_DIRS for seg in rel.split("/")):
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            ext = path.suffix.lower()
            top_level = rel.split("/")[0]
            results.append(FileInfo(path=rel, ext=ext, size=size, top_level=top_level))
    return sorted(results, key=lambda f: f.path)


def detect_stack(root: Path, files: list[FileInfo]) -> dict[str, list[str]]:
    present = {f.path for f in files}
    lower_present = {p.lower() for p in present}
    stack: dict[str, list[str]] = defaultdict(list)

    def has(name: str) -> bool:
        return name.lower() in lower_present

    if has("package.json"):
        stack["runtime"].append("Node.js")
    if has("pyproject.toml") or has("requirements.txt") or has("Pipfile"):
        stack["runtime"].append("Python")
    if has("Cargo.toml"):
        stack["runtime"].append("Rust")
    if has("go.mod"):
        stack["runtime"].append("Go")
    if has("pom.xml") or has("build.gradle") or has("settings.gradle"):
        stack["runtime"].append("JVM")
    if has("composer.json"):
        stack["runtime"].append("PHP")
    if has("Gemfile"):
        stack["runtime"].append("Ruby")

    pkg = root / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
            deps = set((data.get("dependencies") or {}).keys()) | set((data.get("devDependencies") or {}).keys())
            for dep, label in [
                ("next", "Next.js"),
                ("react", "React"),
                ("vue", "Vue"),
                ("svelte", "Svelte"),
                ("@nestjs/core", "NestJS"),
                ("express", "Express"),
                ("fastify", "Fastify"),
                ("vite", "Vite"),
                ("expo", "Expo"),
                ("react-native", "React Native"),
                ("electron", "Electron"),
                ("tailwindcss", "Tailwind CSS"),
                ("typescript", "TypeScript"),
                ("jest", "Jest"),
                ("vitest", "Vitest"),
                ("playwright", "Playwright"),
                ("cypress", "Cypress"),
            ]:
                if dep in deps:
                    stack["frameworks"].append(label)
        except Exception:
            pass

    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        text = load_text(pyproject) or ""
        for needle, label in [
            ("django", "Django"),
            ("flask", "Flask"),
            ("fastapi", "FastAPI"),
            ("pytest", "Pytest"),
            ("sqlalchemy", "SQLAlchemy"),
        ]:
            if needle in text.lower():
                stack["frameworks"].append(label)

    if has("docker-compose.yml") or has("docker-compose.yaml"):
        stack["tooling"].append("Docker Compose")
    if has("Dockerfile"):
        stack["tooling"].append("Docker")
    if has(".github/workflows"):
        stack["tooling"].append("GitHub Actions")

    for key in list(stack.keys()):
        stack[key] = sorted(set(stack[key]))
    return dict(stack)


def extract_commands(root: Path) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []

    pkg = root / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
            scripts = data.get("scripts") or {}
            for name, cmd in scripts.items():
                rows.append(("package.json", name, str(cmd)))
        except Exception:
            pass

    makefile = root / "Makefile"
    if makefile.exists():
        text = load_text(makefile) or ""
        for line in text.splitlines():
            m = re.match(r"^([A-Za-z0-9_.\-]+):(?:\s|$)", line)
            if not m:
                continue
            target = m.group(1)
            if target.startswith("."):
                continue
            rows.append(("Makefile", target, f"make {target}"))

    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        text = load_text(pyproject) or ""
        in_scripts = False
        for line in text.splitlines():
            stripped = line.strip()
            if stripped in {"[project.scripts]", "[tool.poetry.scripts]"}:
                in_scripts = True
                continue
            if in_scripts and stripped.startswith("["):
                in_scripts = False
            if in_scripts and "=" in stripped and not stripped.startswith("#"):
                name = stripped.split("=", 1)[0].strip()
                rows.append(("pyproject.toml", name, stripped))

    return sorted(set(rows))


def likely_important_files(files: list[FileInfo]) -> list[str]:
    candidates: set[str] = set()
    for f in files:
        name = f.path.split("/")[-1]
        if name in IMPORTANT_FILE_PATTERNS or f.path in IMPORTANT_FILE_PATTERNS:
            candidates.add(f.path)
        if any(part in {"README.md", "CLAUDE.md"} for part in f.path.split("/")):
            candidates.add(f.path)
        if f.path.count("/") <= 1 and f.ext in {".json", ".toml", ".yml", ".yaml", ".md", ".py", ".ts", ".tsx", ".js"}:
            candidates.add(f.path)

    scored = []
    for path in candidates:
        score = 0
        base = path.split("/")[-1]
        if base in {"README.md", "CLAUDE.md"}:
            score += 50
        if any(token in base.lower() for token in ["config", "main", "server", "app", "route", "docker", "package", "pyproject"]):
            score += 20
        score += max(0, 10 - path.count("/"))
        scored.append((score, path))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [p for _, p in scored[:MAX_IMPORTANT_FILES]]


def likely_entrypoints(files: list[FileInfo]) -> list[str]:
    candidates: list[tuple[int, str]] = []
    for f in files:
        base = Path(f.path).stem.lower()
        filename = Path(f.path).name.lower()
        score = 0
        if any(hint == base for hint in ENTRYPOINT_NAME_HINTS):
            score += 30
        if any(hint in filename for hint in ENTRYPOINT_NAME_HINTS):
            score += 10
        if filename in {
            "package.json", "pyproject.toml", "go.mod", "cargo.toml", "dockerfile",
            "next.config.js", "next.config.mjs", "next.config.ts", "vite.config.ts", "vite.config.js"
        }:
            score += 20
        if f.path.startswith("src/"):
            score += 5
        if score > 0:
            candidates.append((score, f.path))
    candidates.sort(key=lambda x: (-x[0], x[1]))
    seen = []
    for _, p in candidates:
        if p not in seen:
            seen.append(p)
    return seen[:40]


def infer_area_label(path: str) -> str:
    p = path.lower()
    if any(token in p for token in ["test", "spec", "__tests__", "cypress", "playwright"]):
        return "tests"
    if any(token in p for token in ["route", "router", "controller", "handler", "api"]):
        return "api or routing"
    if any(token in p for token in ["component", "ui", "page", "screen", "view"]):
        return "frontend or user interface"
    if any(token in p for token in ["service", "worker", "job", "queue", "consumer"]):
        return "services or background jobs"
    if any(token in p for token in ["model", "schema", "db", "migration", "prisma", "sql"]):
        return "data or persistence"
    if any(token in p for token in ["config", "settings", "env", "docker", "compose", "yaml", "toml"]):
        return "configuration"
    return "general code or assets"


def build_areas(files: list[FileInfo]) -> dict[str, dict[str, object]]:
    grouped: dict[str, list[FileInfo]] = defaultdict(list)
    for f in files:
        grouped[f.top_level].append(f)

    areas: dict[str, dict[str, object]] = {}
    for top, group in sorted(grouped.items()):
        exts = Counter(f.ext or "[no extension]" for f in group)
        sample_paths = [g.path for g in group[:8]]
        label_votes = Counter(infer_area_label(g.path) for g in group[:40])
        areas[top] = {
            "file_count": len(group),
            "common_extensions": [ext for ext, _ in exts.most_common(6)],
            "inferred_role": label_votes.most_common(1)[0][0] if label_votes else "unknown",
            "sample_paths": sample_paths,
        }
    return areas


def extract_symbols_from_text(path: str, text: str) -> list[str]:
    ext = Path(path).suffix.lower()
    lines = text.splitlines()
    symbols: list[str] = []

    patterns: list[re.Pattern[str]] = []
    if ext == ".py":
        patterns = [
            re.compile(r"^class\s+([A-Za-z_][A-Za-z0-9_]*)"),
            re.compile(r"^def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("),
        ]
    elif ext in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}:
        patterns = [
            re.compile(r"^(?:export\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)"),
            re.compile(r"^(?:export\s+)?function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("),
            re.compile(r"^(?:export\s+)?const\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:async\s*)?\("),
            re.compile(r"^(?:export\s+)?const\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:async\s*)?[A-Za-z_][A-Za-z0-9_]*\s*=>"),
        ]
    elif ext == ".go":
        patterns = [
            re.compile(r"^type\s+([A-Za-z_][A-Za-z0-9_]*)\s+struct"),
            re.compile(r"^func\s+(?:\([^)]+\)\s*)?([A-Za-z_][A-Za-z0-9_]*)\s*\("),
        ]
    elif ext in {".java", ".kt", ".kts", ".cs", ".php", ".rb", ".rs", ".swift"}:
        patterns = [
            re.compile(r"^(?:public\s+|private\s+|protected\s+|internal\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)"),
            re.compile(r"^(?:public\s+|private\s+|protected\s+|internal\s+)?(?:static\s+)?(?:fn|func|def|void|int|bool|String|Task|Result|async\s+fn)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("),
        ]

    route_patterns = [
        re.compile(r"\b(app|get|post|put|patch|delete|router)\.(get|post|put|patch|delete)\s*\(\s*['\"]([^'\"]+)['\"]"),
        re.compile(r"path\s*[:=]\s*['\"]([^'\"]+)['\"]"),
    ]

    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("//"):
            continue
        for pat in patterns:
            m = pat.search(line)
            if m:
                symbols.append(m.group(1))
                break
        for pat in route_patterns:
            m = pat.search(line)
            if not m:
                continue
            value = m.group(m.lastindex or 1)
            if value.startswith("/"):
                symbols.append(f"route {value}")
        if len(symbols) >= MAX_SYMBOLS_PER_FILE:
            break

    deduped: list[str] = []
    seen = set()
    for s in symbols:
        if s in seen:
            continue
        seen.add(s)
        deduped.append(s)
    return deduped[:MAX_SYMBOLS_PER_FILE]


def build_symbol_index(root: Path, files: list[FileInfo]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for f in files:
        if f.size > MAX_TEXT_FILE_BYTES:
            continue
        if f.ext.lower() not in {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".go", ".java", ".kt", ".kts", ".cs", ".php", ".rb", ".rs", ".swift"}:
            continue
        text = load_text(root / f.path)
        if not text:
            continue
        symbols = extract_symbols_from_text(f.path, text)
        if symbols:
            out[f.path] = symbols
    return out


def render_tree(files: list[FileInfo]) -> str:
    tree: dict = {}
    for f in files:
        node = tree
        for part in f.path.split("/"):
            node = node.setdefault(part, {})

    lines: list[str] = []

    def walk(node: dict, prefix: str = "") -> None:
        for i, key in enumerate(sorted(node.keys())):
            if len(lines) >= MAX_TREE_LINES:
                return
            connector = "└── " if i == len(node) - 1 else "├── "
            lines.append(prefix + connector + key)
            next_prefix = prefix + ("    " if i == len(node) - 1 else "│   ")
            walk(node[key], next_prefix)

    walk(tree)
    if len(lines) >= MAX_TREE_LINES:
        lines.append("… tree truncated …")
    return "\n".join(lines)


def write_markdown(path: Path, content: str) -> None:
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def main() -> int:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
    out_dir = root / ".claude" / "project-context"
    out_dir.mkdir(parents=True, exist_ok=True)

    files = walk_files(root)
    stack = detect_stack(root, files)
    commands = extract_commands(root)
    important_files = likely_important_files(files)
    entrypoints = likely_entrypoints(files)
    areas = build_areas(files)
    symbol_index = build_symbol_index(root, files)
    tree = render_tree(files)

    ext_counts = Counter(f.ext or "[no extension]" for f in files)
    top_level_counts = Counter(f.top_level for f in files)
    total_bytes = sum(f.size for f in files)

    manifest = {
        "generated_at_utc": utc_now_iso(),
        "root": str(root),
        "file_count": len(files),
        "total_bytes": total_bytes,
        "top_level_folders": top_level_counts.most_common(25),
        "extension_counts": ext_counts.most_common(25),
        "stack": stack,
        "important_files_count": len(important_files),
        "entrypoints_count": len(entrypoints),
        "symbol_index_files": len(symbol_index),
    }

    overview = f"""
# Project Overview

Generated: {manifest['generated_at_utc']}
Root: `{root}`

## Repo shape

- Total files considered: **{len(files)}**
- Approx total size considered: **{total_bytes:,} bytes**
- Most common extensions: {", ".join(f'`{ext}` ({count})' for ext, count in ext_counts.most_common(10))}
- Largest top-level areas: {", ".join(f'`{name}` ({count})' for name, count in top_level_counts.most_common(10))}

## Detected stack

- Runtime/platforms: {", ".join(stack.get('runtime', []) or ['unknown'])}
- Frameworks: {", ".join(stack.get('frameworks', []) or ['none confidently detected'])}
- Tooling: {", ".join(stack.get('tooling', []) or ['none confidently detected'])}

## Most likely first-read files

""" + "\n".join(f"- `{p}`" for p in important_files[:20]) + """

## Notes

- This file is deterministic and heuristic-based.
- Treat framework and entrypoint detection as probable, not authoritative.
- Use `ENTRYPOINTS.md`, `COMMANDS.md`, and `AREAS.md` to narrow task scope before broad search.
"""
    write_markdown(out_dir / "OVERVIEW.md", overview)

    stack_md = [
        "# Stack Detection",
        "",
        "## Runtime/platforms",
        "",
        *(f"- {item}" for item in (stack.get("runtime") or ["unknown"])),
        "",
        "## Frameworks and libraries",
        "",
        *(f"- {item}" for item in (stack.get("frameworks") or ["none confidently detected"])),
        "",
        "## Tooling",
        "",
        *(f"- {item}" for item in (stack.get("tooling") or ["none confidently detected"])),
        "",
        "## Language hints",
        "",
        *(f"- `{ext}`: {count} files" for ext, count in ext_counts.most_common(15)),
        "",
        "## Interpretation",
        "",
        "- Use this file to confirm the likely tech stack before making assumptions about commands, routing, testing, or build behavior.",
        "- For mixed stacks, route tasks by area ownership rather than by file extension alone.",
    ]
    write_markdown(out_dir / "STACK.md", "\n".join(stack_md))

    cmd_body = "\n".join(f"- `{source}` · **{name}** → `{cmd}`" for source, name, cmd in commands) or "- No commands extracted confidently."
    write_markdown(out_dir / "COMMANDS.md", f"# Commands\n\nThese commands were extracted from real project files when possible.\n\n{cmd_body}\n")

    entry_body = "\n".join(f"- `{p}`" for p in entrypoints) or "- No clear entrypoints detected."
    write_markdown(out_dir / "ENTRYPOINTS.md", f"# Likely Entrypoints and Key Config\n\nThese are probable runtime starts, route surfaces, or configuration anchors.\n\n{entry_body}\n")

    area_lines = ["# Top-Level Areas", ""]
    for name, meta in areas.items():
        area_lines.append(f"## `{name}`")
        area_lines.append(f"- Inferred role: **{meta['inferred_role']}**")
        area_lines.append(f"- File count: **{meta['file_count']}**")
        area_lines.append(f"- Common extensions: {', '.join(f'`{x}`' for x in meta['common_extensions'])}")
        area_lines.append("- Sample paths:")
        for p in meta["sample_paths"]:
            area_lines.append(f"  - `{p}`")
        area_lines.append("")
    write_markdown(out_dir / "AREAS.md", "\n".join(area_lines))

    write_markdown(out_dir / "IMPORTANT_FILES.md", "# Important Files\n\n" + "\n".join(f"- `{p}`" for p in important_files))

    symbol_lines = ["# Symbol Index", "", "Best-effort top-level symbols and route hints extracted from source files.", ""]
    for path, symbols in sorted(symbol_index.items()):
        symbol_lines.append(f"## `{path}`")
        for sym in symbols:
            symbol_lines.append(f"- `{sym}`")
        symbol_lines.append("")
    if len(symbol_lines) <= 4:
        symbol_lines.append("No symbols extracted confidently.")
    write_markdown(out_dir / "SYMBOL_INDEX.md", "\n".join(symbol_lines))

    (out_dir / "DIRECTORY_TREE.txt").write_text(tree + "\n", encoding="utf-8")
    (out_dir / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    with (out_dir / "FILES.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["path", "extension", "size_bytes", "top_level"])
        for row in files:
            writer.writerow([row.path, row.ext, row.size, row.top_level])

    print(f"Wrote project context pack to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
