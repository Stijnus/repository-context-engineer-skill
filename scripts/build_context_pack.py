#!/usr/bin/env python3
from __future__ import annotations

import csv
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

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
}

DEFAULT_IGNORE_PATH_PREFIXES = {
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
    "README.md", "CLAUDE.md", "AGENTS.md", "package.json", "pnpm-workspace.yaml", "turbo.json", "nx.json",
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
MAX_TOKEN_ROWS = 100
MAX_ROUTING_HINTS = 80


@dataclass
class FileInfo:
    path: str
    ext: str
    size: int
    top_level: str
    mtime_ns: int = 0


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def estimate_tokens_from_text(text: str) -> int:
    return max(1, len(text) // 4)


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


def estimate_tokens_for_file(root: Path, file: FileInfo) -> int:
    text = load_text(root / file.path)
    if text is not None:
        return estimate_tokens_from_text(text)
    return max(1, file.size // 4)


def load_gitignore_patterns(root: Path) -> list[str]:
    patterns: list[str] = []
    for rel in [".gitignore", ".git/info/exclude"]:
        path = root / rel
        if not path.exists():
            continue
        try:
            for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or line.startswith("!"):
                    continue
                patterns.append(line)
        except Exception:
            continue
    return patterns


def matches_ignore_pattern(rel_path: str, pattern: str) -> bool:
    rel = rel_path.strip("/")
    pat = pattern.strip()
    if not pat:
        return False

    dir_only = pat.endswith("/")
    if dir_only:
        pat = pat[:-1]

    pat = pat.lstrip("./")
    rel_parts = rel.split("/")

    if "/" not in pat:
        if fnmatch.fnmatch(Path(rel).name, pat):
            return True
        if dir_only and pat in rel_parts:
            return True
        return False

    if fnmatch.fnmatch(rel, pat):
        return True
    if fnmatch.fnmatch("/" + rel, pat):
        return True
    if fnmatch.fnmatch(rel, f"**/{pat}"):
        return True
    if dir_only and (rel == pat or rel.startswith(f"{pat}/") or f"/{pat}/" in f"/{rel}/"):
        return True
    return False


def walk_files(root: Path) -> list[FileInfo]:
    gitignore_patterns = load_gitignore_patterns(root)
    results: list[FileInfo] = []

    def is_ignored_path(rel_path: str) -> bool:
        if any(rel_path == prefix or rel_path.startswith(f"{prefix}/") for prefix in DEFAULT_IGNORE_PATH_PREFIXES):
            return True
        return any(matches_ignore_pattern(rel_path, pat) for pat in gitignore_patterns)

    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root)
        parts = [] if rel_dir == "." else rel_dir.split(os.sep)
        rel_dir_posix = "." if rel_dir == "." else Path(rel_dir).as_posix()
        dirnames[:] = [
            d
            for d in dirnames
            if d not in DEFAULT_IGNORE_DIRS
            and not d.startswith(".DS_")
            and not is_ignored_path(d if rel_dir_posix == "." else f"{rel_dir_posix}/{d}")
        ]
        if any(part in DEFAULT_IGNORE_DIRS for part in parts):
            dirnames[:] = []
            continue
        if rel_dir_posix != "." and is_ignored_path(rel_dir_posix):
            dirnames[:] = []
            continue

        for filename in filenames:
            path = Path(dirpath) / filename
            rel = path.relative_to(root).as_posix()
            if is_ignored_path(rel):
                continue
            if any(seg in DEFAULT_IGNORE_DIRS for seg in rel.split("/")):
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            results.append(
                FileInfo(
                    path=rel,
                    ext=path.suffix.lower(),
                    size=stat.st_size,
                    top_level=rel.split("/")[0],
                    mtime_ns=stat.st_mtime_ns,
                )
            )
    return sorted(results, key=lambda f: f.path)


def compute_fingerprint(files: list[FileInfo]) -> str:
    digest = hashlib.sha256()
    for file_info in files:
        digest.update(file_info.path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(file_info.size).encode("ascii"))
        digest.update(b"\0")
        digest.update(str(file_info.mtime_ns).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def detect_stack(root: Path, files: list[FileInfo]) -> dict[str, list[str]]:
    present = {f.path for f in files}
    lower_present = {path.lower() for path in present}
    stack: dict[str, list[str]] = defaultdict(list)

    def has(name: str) -> bool:
        return name.lower() in lower_present

    if has("package.json"):
        stack["runtime"].append("Node.js")
    if has("pyproject.toml") or has("requirements.txt") or has("Pipfile") or any(f.ext == ".py" for f in files):
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
    if any(path.startswith(".github/workflows/") for path in lower_present):
        stack["tooling"].append("GitHub Actions")
    if any(f.path.startswith("scripts/") and f.ext == ".py" for f in files):
        stack["tooling"].append("Python scripts")

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
            match = re.match(r"^([A-Za-z0-9_.\-]+):(?:\s|$)", line)
            if not match:
                continue
            target = match.group(1)
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
    for file_info in files:
        name = file_info.path.split("/")[-1]
        if name in IMPORTANT_FILE_PATTERNS or file_info.path in IMPORTANT_FILE_PATTERNS:
            candidates.add(file_info.path)
        if any(part in {"README.md", "CLAUDE.md", "AGENTS.md"} for part in file_info.path.split("/")):
            candidates.add(file_info.path)
        if file_info.path.count("/") <= 1 and file_info.ext in {".json", ".toml", ".yml", ".yaml", ".md", ".py", ".ts", ".tsx", ".js"}:
            candidates.add(file_info.path)

    scored: list[tuple[int, str]] = []
    for path in candidates:
        score = 0
        base = path.split("/")[-1]
        if base in {"README.md", "CLAUDE.md", "AGENTS.md"}:
            score += 50
        if any(token in base.lower() for token in ["config", "main", "server", "app", "route", "docker", "package", "pyproject"]):
            score += 20
        score += max(0, 10 - path.count("/"))
        scored.append((score, path))
    scored.sort(key=lambda row: (-row[0], row[1]))
    return [path for _, path in scored[:MAX_IMPORTANT_FILES]]


def likely_entrypoints(files: list[FileInfo]) -> list[str]:
    candidates: list[tuple[int, str]] = []
    for file_info in files:
        base = Path(file_info.path).stem.lower()
        filename = Path(file_info.path).name.lower()
        score = 0
        if any(hint == base for hint in ENTRYPOINT_NAME_HINTS):
            score += 30
        if any(hint in filename for hint in ENTRYPOINT_NAME_HINTS):
            score += 10
        if filename in {
            "package.json",
            "pyproject.toml",
            "go.mod",
            "cargo.toml",
            "dockerfile",
            "next.config.js",
            "next.config.mjs",
            "next.config.ts",
            "vite.config.ts",
            "vite.config.js",
        }:
            score += 20
        if file_info.path.startswith("src/"):
            score += 5
        if score > 0:
            candidates.append((score, file_info.path))
    candidates.sort(key=lambda row: (-row[0], row[1]))
    seen: list[str] = []
    for _, path in candidates:
        if path not in seen:
            seen.append(path)
    return seen[:40]


def path_tokens(path: str) -> set[str]:
    return {token for token in re.split(r"[/_.\-\s]+", path.lower()) if token}


def infer_area_label(path: str) -> str:
    tokens = path_tokens(path)
    top = path.lower().split("/", 1)[0]
    if top in {"scripts", "tools", "bin", "tasks"} or tokens & {"script", "scripts", "tool", "tools", "cli"}:
        return "tooling or automation"
    if tokens & {"test", "tests", "spec", "specs", "__tests__", "cypress", "playwright"}:
        return "tests"
    if tokens & {"route", "routes", "router", "controller", "controllers", "handler", "handlers", "api"}:
        return "api or routing"
    if tokens & {"component", "components", "ui", "page", "pages", "screen", "screens", "view", "views"}:
        return "frontend or user interface"
    if tokens & {"service", "services", "worker", "workers", "job", "jobs", "queue", "consumer"}:
        return "services or background jobs"
    if tokens & {"model", "models", "schema", "schemas", "db", "database", "migration", "migrations", "prisma", "sql"}:
        return "data or persistence"
    if tokens & {"config", "configs", "settings", "env", "docker", "compose", "yaml", "yml", "toml"}:
        return "configuration"
    return "general code or assets"


def build_areas(files: list[FileInfo]) -> dict[str, dict[str, object]]:
    grouped: dict[str, list[FileInfo]] = defaultdict(list)
    for file_info in files:
        grouped[file_info.top_level].append(file_info)

    areas: dict[str, dict[str, object]] = {}
    for top, group in sorted(grouped.items()):
        exts = Counter(file_info.ext or "[no extension]" for file_info in group)
        sample_paths = [file_info.path for file_info in group[:8]]
        label_votes = Counter(infer_area_label(file_info.path) for file_info in group[:40])
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
        for pattern in patterns:
            match = pattern.search(line)
            if match:
                symbols.append(match.group(1))
                break
        for pattern in route_patterns:
            match = pattern.search(line)
            if not match:
                continue
            value = match.group(match.lastindex or 1)
            if value.startswith("/"):
                symbols.append(f"route {value}")
        if len(symbols) >= MAX_SYMBOLS_PER_FILE:
            break

    deduped: list[str] = []
    seen = set()
    for symbol in symbols:
        if symbol in seen:
            continue
        seen.add(symbol)
        deduped.append(symbol)
    return deduped[:MAX_SYMBOLS_PER_FILE]


def build_symbol_index(root: Path, files: list[FileInfo]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for file_info in files:
        if file_info.size > MAX_TEXT_FILE_BYTES:
            continue
        if file_info.ext.lower() not in {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".go", ".java", ".kt", ".kts", ".cs", ".php", ".rb", ".rs", ".swift"}:
            continue
        text = load_text(root / file_info.path)
        if not text:
            continue
        symbols = extract_symbols_from_text(file_info.path, text)
        if symbols:
            out[file_info.path] = symbols
    return out


def build_token_counts(root: Path, files: list[FileInfo]) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    by_file: list[tuple[str, int]] = []
    by_dir: Counter[str] = Counter()
    for file_info in files:
        tokens = estimate_tokens_for_file(root, file_info)
        by_file.append((file_info.path, tokens))
        parts = file_info.path.split("/")
        for i in range(1, len(parts)):
            by_dir["/".join(parts[:i])] += tokens
        by_dir["."] += tokens
    by_file.sort(key=lambda row: (-row[1], row[0]))
    dir_rows = sorted(by_dir.items(), key=lambda row: (-row[1], row[0]))
    return by_file[:MAX_TOKEN_ROWS], dir_rows[:MAX_TOKEN_ROWS]


def build_task_routing(files: list[FileInfo], symbol_index: dict[str, list[str]], areas: dict[str, dict[str, object]]) -> dict[str, list[str]]:
    stop = {
        "src", "app", "apps", "packages", "pkg", "lib", "libs", "core", "shared", "common", "components",
        "pages", "page", "routes", "route", "api", "server", "client", "frontend", "backend", "service",
        "services", "module", "modules", "internal", "public", "private", "utils", "util", "helpers",
        "tests", "test", "spec", "docs", "doc", "scripts", "config", "configs",
    }
    hits: dict[str, Counter[str]] = defaultdict(Counter)
    token_re = re.compile(r"[a-zA-Z][a-zA-Z0-9_-]{2,}")

    for top in areas:
        key = top.lower().replace("_", "-")
        if key not in stop and len(key) >= 3:
            hits[key][f"{top}/"] += 3

    for file_info in files:
        path = file_info.path.lower()
        for token in set(token_re.findall(path)):
            if token in stop:
                continue
            weight = 1
            if any(mark in token for mark in [
                "auth", "billing", "payment", "invoice", "login", "user", "account", "profile", "admin", "search",
                "cart", "order", "checkout", "notification", "email", "sms", "chat", "message", "onboarding",
                "settings", "report", "analytics", "schema", "migration", "worker", "queue",
            ]):
                weight += 2
            hits[token][file_info.path] += weight
        for symbol in symbol_index.get(file_info.path, [])[:10]:
            for token in token_re.findall(symbol.lower()):
                if token in stop:
                    continue
                hits[token][file_info.path] += 1

    result: dict[str, list[str]] = {}
    for key, counter in hits.items():
        ranked = [path for path, _ in counter.most_common(8)]
        if ranked:
            result[key] = ranked
    return dict(sorted(result.items())[:MAX_ROUTING_HINTS])


def collect_git_hotspots(root: Path, limit: int = 200) -> dict[str, object]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "log", f"-n{limit}", "--name-only", "--pretty=format:__COMMIT__"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        )
    except Exception:
        return {"available": False, "reason": "git not available"}

    if proc.returncode != 0 or not proc.stdout.strip():
        return {"available": False, "reason": "git log unavailable"}

    file_counts: Counter[str] = Counter()
    cochange: Counter[tuple[str, str]] = Counter()
    current_files: set[str] = set()
    for raw in proc.stdout.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line == "__COMMIT__":
            ordered = sorted(current_files)
            for i in range(len(ordered)):
                for j in range(i + 1, len(ordered)):
                    cochange[(ordered[i], ordered[j])] += 1
            current_files = set()
            continue
        current_files.add(line)
        file_counts[line] += 1

    return {
        "available": True,
        "top_files": file_counts.most_common(30),
        "top_pairs": [
            {"a": a, "b": b, "count": count}
            for (a, b), count in sorted(cochange.items(), key=lambda row: (-row[1], row[0]))[:20]
        ],
    }


def render_tree(files: list[FileInfo]) -> str:
    tree: dict = {}
    for file_info in files:
        node = tree
        for part in file_info.path.split("/"):
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


def build_pack(root: Path) -> dict[str, object]:
    out_dir = root / ".claude" / "project-context"
    out_dir.mkdir(parents=True, exist_ok=True)

    files = walk_files(root)
    stack = detect_stack(root, files)
    commands = extract_commands(root)
    important_files = likely_important_files(files)
    entrypoints = likely_entrypoints(files)
    areas = build_areas(files)
    symbol_index = build_symbol_index(root, files)
    token_files, token_dirs = build_token_counts(root, files)
    task_routing = build_task_routing(files, symbol_index, areas)
    git_hotspots = collect_git_hotspots(root)
    tree = render_tree(files)
    fingerprint = compute_fingerprint(files)

    ext_counts = Counter(file_info.ext or "[no extension]" for file_info in files)
    top_level_counts = Counter(file_info.top_level for file_info in files)
    total_bytes = sum(file_info.size for file_info in files)

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
        "fingerprint": fingerprint,
        "supports_check_stale": True,
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

""" + "\n".join(f"- `{path}`" for path in important_files[:20]) + """

## V2 notes

- This file is deterministic and heuristic-based.
- V2 adds token concentration, task-routing hints, change hotspots, and a staleness fingerprint.
- Use `TASK_ROUTING.md`, `TOKEN_COUNTS.md`, and `CHANGE_HOTSPOTS.md` to reduce blind repo-wide search.
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

    entry_body = "\n".join(f"- `{path}`" for path in entrypoints) or "- No clear entrypoints detected."
    write_markdown(out_dir / "ENTRYPOINTS.md", f"# Likely Entrypoints and Key Config\n\nThese are probable runtime starts, route surfaces, or configuration anchors.\n\n{entry_body}\n")

    area_lines = ["# Top-Level Areas", ""]
    for name, meta in areas.items():
        area_lines.append(f"## `{name}`")
        area_lines.append(f"- Inferred role: **{meta['inferred_role']}**")
        area_lines.append(f"- File count: **{meta['file_count']}**")
        area_lines.append(f"- Common extensions: {', '.join(f'`{value}`' for value in meta['common_extensions'])}")
        area_lines.append("- Sample paths:")
        for path in meta["sample_paths"]:
            area_lines.append(f"  - `{path}`")
        area_lines.append("")
    write_markdown(out_dir / "AREAS.md", "\n".join(area_lines))

    write_markdown(out_dir / "IMPORTANT_FILES.md", "# Important Files\n\n" + "\n".join(f"- `{path}`" for path in important_files))

    symbol_lines = ["# Symbol Index", "", "Best-effort top-level symbols and route hints extracted from source files.", ""]
    for path, symbols in sorted(symbol_index.items()):
        symbol_lines.append(f"## `{path}`")
        for symbol in symbols:
            symbol_lines.append(f"- `{symbol}`")
        symbol_lines.append("")
    if len(symbol_lines) <= 4:
        symbol_lines.append("No symbols extracted confidently.")
    write_markdown(out_dir / "SYMBOL_INDEX.md", "\n".join(symbol_lines))

    token_lines = [
        "# Token Counts",
        "",
        "Approximate token concentration to help avoid blowing context on the wrong files.",
        "",
        "## Heaviest directories",
        "",
    ]
    for path, tokens in token_dirs[:30]:
        token_lines.append(f"- `{path}` → ~{tokens:,} tokens")
    token_lines.extend(["", "## Heaviest files", ""])
    for path, tokens in token_files[:40]:
        token_lines.append(f"- `{path}` → ~{tokens:,} tokens")
    token_lines.extend([
        "",
        "## How to use this",
        "",
        "- Start with lighter, high-signal files when possible.",
        "- Avoid loading token-heavy files until the routing layer points to them.",
        "- Use this file to budget context and pick compressed summaries first.",
    ])
    write_markdown(out_dir / "TOKEN_COUNTS.md", "\n".join(token_lines))

    routing_lines = [
        "# Task Routing",
        "",
        "Use this as a first-pass domain map before broad search.",
        "",
        "## Suggested domains",
        "",
    ]
    if not task_routing:
        routing_lines.append("- No strong routing hints extracted.")
    else:
        for domain, paths in task_routing.items():
            routing_lines.append(f"## `{domain}`")
            for path in paths:
                routing_lines.append(f"- `{path}`")
            routing_lines.append("")
    routing_lines.extend([
        "## How to use this",
        "",
        "1. Match the user's request to one or more domains above.",
        "2. Search only those folders/files first.",
        "3. Expand scope only if the first pass is weak or contradictory.",
    ])
    write_markdown(out_dir / "TASK_ROUTING.md", "\n".join(routing_lines))

    hotspot_lines = [
        "# Change Hotspots",
        "",
        "Git-derived hints about files that change often and files that often change together.",
        "",
    ]
    if not git_hotspots.get("available"):
        hotspot_lines.append(f"- Hotspot data unavailable: {git_hotspots.get('reason', 'unknown reason')}")
    else:
        hotspot_lines.extend(["## Frequently changed files", ""])
        for path, count in git_hotspots["top_files"]:
            hotspot_lines.append(f"- `{path}` → {count} recent commits")
        hotspot_lines.extend(["", "## Files that often change together", ""])
        for row in git_hotspots["top_pairs"]:
            hotspot_lines.append(f"- `{row['a']}` + `{row['b']}` → {row['count']} co-changes")
    hotspot_lines.extend([
        "",
        "## How to use this",
        "",
        "- When editing one hotspot file, check its common co-change partners.",
        "- Use this as a test/config discovery hint, not a correctness guarantee.",
    ])
    write_markdown(out_dir / "CHANGE_HOTSPOTS.md", "\n".join(hotspot_lines))

    staleness_lines = [
        "# Staleness",
        "",
        f"- Generated at: `{manifest['generated_at_utc']}`",
        f"- Fingerprint: `{fingerprint}`",
        "",
        "## Check command",
        "",
        "Run this to see whether the current repo still matches the manifest:",
        "",
        "```bash",
        "python scripts/build_context_pack.py . --check-stale",
        "```",
        "",
        "If the fingerprint changed, refresh the pack before relying on it for structural guidance.",
    ]
    write_markdown(out_dir / "STALENESS.md", "\n".join(staleness_lines))

    (out_dir / "DIRECTORY_TREE.txt").write_text(tree + "\n", encoding="utf-8")
    (out_dir / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    with (out_dir / "FILES.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["path", "extension", "size_bytes", "top_level"])
        for row in files:
            writer.writerow([row.path, row.ext, row.size, row.top_level])

    return manifest


def check_stale(root: Path) -> int:
    manifest_path = root / ".claude" / "project-context" / "MANIFEST.json"
    if not manifest_path.exists():
        print("STALE: manifest missing")
        return 2
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        print("STALE: manifest unreadable")
        return 2

    current_files = walk_files(root)
    current_fingerprint = compute_fingerprint(current_files)
    old_fingerprint = manifest.get("fingerprint")
    if old_fingerprint == current_fingerprint:
        print("OK: project context pack appears current")
        return 0

    print("STALE: fingerprint changed")
    print(f"old={old_fingerprint}")
    print(f"new={current_fingerprint}")
    return 1


def main() -> int:
    args = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
    flags = {arg for arg in sys.argv[1:] if arg.startswith("--")}
    root = Path(args[0]).resolve() if args else Path.cwd().resolve()

    if "--check-stale" in flags:
        return check_stale(root)

    manifest = build_pack(root)
    print(f"Wrote project context pack to {root / '.claude' / 'project-context'}")
    print(f"Fingerprint: {manifest['fingerprint']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
