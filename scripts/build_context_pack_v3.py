#!/usr/bin/env python3
from __future__ import annotations

import csv
import fnmatch
import hashlib
import json
import math
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_IGNORE_DIRS = {
    ".git", ".hg", ".svn", ".next", ".nuxt", ".turbo", ".vercel", ".idea", ".vscode",
    "node_modules", "dist", "build", "coverage", "vendor", "tmp", "temp", "out",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".pnpm-store", ".yarn", ".cache", ".expo",
    ".gradle", "Pods", "DerivedData", "__pycache__",
}
DEFAULT_IGNORE_PATH_PREFIXES = {".claude/project-context"}
TEXT_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".json", ".jsonc", ".yaml", ".yml", ".toml",
    ".ini", ".cfg", ".conf", ".md", ".txt", ".sh", ".bash", ".zsh", ".go", ".rs", ".java", ".kt",
    ".kts", ".php", ".rb", ".cs", ".cpp", ".cc", ".cxx", ".c", ".h", ".hpp", ".swift", ".sql",
    ".graphql", ".gql", ".env", ".example", ".xml", ".html", ".css", ".scss", ".sass", ".less",
    ".vue", ".svelte", ".dart", ".lock", ".gitignore", ".dockerignore",
}
CODE_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".go", ".rs", ".java", ".kt", ".kts", ".php", ".rb", ".cs", ".swift"}
JS_TS_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
IMPORTANT_FILE_PATTERNS = [
    "README.md", "CLAUDE.md", "AGENTS.md", "package.json", "pnpm-workspace.yaml", "turbo.json", "nx.json",
    "pyproject.toml", "requirements.txt", "Pipfile", "poetry.lock", "Cargo.toml", "go.mod", "composer.json",
    "Gemfile", "pom.xml", "build.gradle", "settings.gradle", "Makefile", "Dockerfile", "docker-compose.yml",
    "docker-compose.yaml", ".env.example", ".env.sample", "next.config.js", "next.config.mjs", "next.config.ts",
    "vite.config.ts", "vite.config.js", "tsconfig.json", "jest.config.js", "jest.config.ts", "playwright.config.ts",
    "cypress.config.ts", "app.py", "main.py", "server.py", "manage.py", "main.go", "src/main.ts", "src/index.ts",
    "src/App.tsx",
]
ENTRYPOINT_NAME_HINTS = ["main", "index", "app", "server", "cli", "manage", "program", "routes", "router", "api", "worker"]
TASK_STOPWORDS = {
    "src", "app", "apps", "packages", "pkg", "lib", "libs", "core", "shared", "common", "components", "pages",
    "page", "routes", "route", "api", "server", "client", "frontend", "backend", "service", "services", "module",
    "modules", "internal", "public", "private", "utils", "util", "helpers", "tests", "test", "spec", "docs", "doc",
    "scripts", "script", "config", "configs", "index", "main", "class", "function", "type", "const", "var", "file",
    "files", "folder", "folders",
}
MAX_TEXT_FILE_BYTES = 350_000
MAX_SYMBOLS_PER_FILE = 40
MAX_TREE_LINES = 500
MAX_IMPORTANT_FILES = 80
MAX_TOKEN_ROWS = 100
MAX_ROUTING_HINTS = 100
MAX_QUERY_RESULTS = 30

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


def tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{1,}", text.lower()) if len(t) >= 2]


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
        if path.exists():
            try:
                for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                    line = raw.strip()
                    if line and not line.startswith("#") and not line.startswith("!"):
                        patterns.append(line)
            except Exception:
                pass
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
        return fnmatch.fnmatch(Path(rel).name, pat) or (dir_only and pat in rel_parts)
    return fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch("/" + rel, pat) or fnmatch.fnmatch(rel, f"**/{pat}") or (dir_only and (rel == pat or rel.startswith(f"{pat}/") or f"/{pat}/" in f"/{rel}/"))


def walk_files(root: Path) -> list[FileInfo]:
    gitignore_patterns = load_gitignore_patterns(root)
    results: list[FileInfo] = []
    def is_ignored_path(rel_path: str) -> bool:
        return any(rel_path == prefix or rel_path.startswith(f"{prefix}/") for prefix in DEFAULT_IGNORE_PATH_PREFIXES) or any(matches_ignore_pattern(rel_path, pat) for pat in gitignore_patterns)
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root)
        parts = [] if rel_dir == "." else rel_dir.split(os.sep)
        rel_dir_posix = "." if rel_dir == "." else Path(rel_dir).as_posix()
        dirnames[:] = [d for d in dirnames if d not in DEFAULT_IGNORE_DIRS and not d.startswith(".DS_") and not is_ignored_path(d if rel_dir_posix == "." else f"{rel_dir_posix}/{d}")]
        if any(part in DEFAULT_IGNORE_DIRS for part in parts) or (rel_dir_posix != "." and is_ignored_path(rel_dir_posix)):
            dirnames[:] = []
            continue
        for filename in filenames:
            path = Path(dirpath) / filename
            rel = path.relative_to(root).as_posix()
            if is_ignored_path(rel) or any(seg in DEFAULT_IGNORE_DIRS for seg in rel.split("/")):
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            results.append(FileInfo(rel, path.suffix.lower(), stat.st_size, rel.split("/")[0], stat.st_mtime_ns))
    return sorted(results, key=lambda f: f.path)


def compute_fingerprint(files: list[FileInfo]) -> str:
    h = hashlib.sha256()
    for f in files:
        h.update(f.path.encode())
        h.update(b"\0")
        h.update(str(f.size).encode())
        h.update(b"\0")
        h.update(str(f.mtime_ns).encode())
        h.update(b"\n")
    return h.hexdigest()


def detect_stack(root: Path, files: list[FileInfo]) -> dict[str, list[str]]:
    present = {f.path for f in files}
    lower_present = {p.lower() for p in present}
    stack: dict[str, list[str]] = defaultdict(list)
    has = lambda name: name.lower() in lower_present
    if has("package.json"): stack["runtime"].append("Node.js")
    if has("pyproject.toml") or has("requirements.txt") or has("Pipfile"): stack["runtime"].append("Python")
    if has("Cargo.toml"): stack["runtime"].append("Rust")
    if has("go.mod"): stack["runtime"].append("Go")
    if has("pom.xml") or has("build.gradle") or has("settings.gradle"): stack["runtime"].append("JVM")
    if has("composer.json"): stack["runtime"].append("PHP")
    if has("Gemfile"): stack["runtime"].append("Ruby")
    pkg = root / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
            deps = set((data.get("dependencies") or {}).keys()) | set((data.get("devDependencies") or {}).keys())
            for dep, label in [("next", "Next.js"), ("react", "React"), ("vue", "Vue"), ("svelte", "Svelte"), ("@nestjs/core", "NestJS"), ("express", "Express"), ("fastify", "Fastify"), ("vite", "Vite"), ("expo", "Expo"), ("react-native", "React Native"), ("electron", "Electron"), ("tailwindcss", "Tailwind CSS"), ("typescript", "TypeScript"), ("jest", "Jest"), ("vitest", "Vitest"), ("playwright", "Playwright"), ("cypress", "Cypress")]:
                if dep in deps: stack["frameworks"].append(label)
        except Exception:
            pass
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        text = load_text(pyproject) or ""
        for needle, label in [("django", "Django"), ("flask", "Flask"), ("fastapi", "FastAPI"), ("pytest", "Pytest"), ("sqlalchemy", "SQLAlchemy")]:
            if needle in text.lower(): stack["frameworks"].append(label)
    if has("docker-compose.yml") or has("docker-compose.yaml"): stack["tooling"].append("Docker Compose")
    if has("Dockerfile"): stack["tooling"].append("Docker")
    if any(p.startswith(".github/workflows/") for p in present): stack["tooling"].append("GitHub Actions")
    for k in list(stack.keys()): stack[k] = sorted(set(stack[k]))
    return dict(stack)


def extract_commands(root: Path) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    pkg = root / "package.json"
    if pkg.exists():
        try:
            scripts = (json.loads(pkg.read_text(encoding="utf-8")).get("scripts") or {})
            for name, cmd in scripts.items(): rows.append(("package.json", name, str(cmd)))
        except Exception:
            pass
    makefile = root / "Makefile"
    if makefile.exists():
        text = load_text(makefile) or ""
        for line in text.splitlines():
            m = re.match(r"^([A-Za-z0-9_.\-]+):(?:\s|$)", line)
            if m and not m.group(1).startswith("."):
                rows.append(("Makefile", m.group(1), f"make {m.group(1)}"))
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        text = load_text(pyproject) or ""
        in_scripts = False
        for line in text.splitlines():
            stripped = line.strip()
            if stripped in {"[project.scripts]", "[tool.poetry.scripts]"}: in_scripts = True; continue
            if in_scripts and stripped.startswith("["): in_scripts = False
            if in_scripts and "=" in stripped and not stripped.startswith("#"): rows.append(("pyproject.toml", stripped.split("=", 1)[0].strip(), stripped))
    return sorted(set(rows))


def likely_important_files(files: list[FileInfo]) -> list[str]:
    candidates: set[str] = set()
    for f in files:
        name = f.path.split("/")[-1]
        if name in IMPORTANT_FILE_PATTERNS or f.path in IMPORTANT_FILE_PATTERNS: candidates.add(f.path)
        if any(part in {"README.md", "CLAUDE.md", "AGENTS.md"} for part in f.path.split("/")): candidates.add(f.path)
        if f.path.count("/") <= 1 and f.ext in {".json", ".toml", ".yml", ".yaml", ".md", ".py", ".ts", ".tsx", ".js"}: candidates.add(f.path)
    scored = []
    for path in candidates:
        base = path.split("/")[-1]
        score = (50 if base in {"README.md", "CLAUDE.md", "AGENTS.md"} else 0) + (20 if any(token in base.lower() for token in ["config", "main", "server", "app", "route", "docker", "package", "pyproject"]) else 0) + max(0, 10 - path.count("/"))
        scored.append((score, path))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [p for _, p in scored[:MAX_IMPORTANT_FILES]]


def likely_entrypoints(files: list[FileInfo]) -> list[str]:
    candidates: list[tuple[int, str]] = []
    for f in files:
        base = Path(f.path).stem.lower(); filename = Path(f.path).name.lower(); score = 0
        if any(hint == base for hint in ENTRYPOINT_NAME_HINTS): score += 30
        if any(hint in filename for hint in ENTRYPOINT_NAME_HINTS): score += 10
        if filename in {"package.json", "pyproject.toml", "go.mod", "cargo.toml", "dockerfile", "next.config.js", "next.config.mjs", "next.config.ts", "vite.config.ts", "vite.config.js"}: score += 20
        if f.path.startswith("src/"): score += 5
        if score > 0: candidates.append((score, f.path))
    candidates.sort(key=lambda x: (-x[0], x[1]))
    out: list[str] = []
    for _, p in candidates:
        if p not in out: out.append(p)
    return out[:40]


def infer_area_label(path: str) -> str:
    p = path.lower()
    if any(t in p for t in ["test", "spec", "__tests__", "cypress", "playwright"]): return "tests"
    if any(t in p for t in ["route", "router", "controller", "handler", "api"]): return "api or routing"
    if any(t in p for t in ["component", "ui", "page", "screen", "view"]): return "frontend or user interface"
    if any(t in p for t in ["service", "worker", "job", "queue", "consumer"]): return "services or background jobs"
    if any(t in p for t in ["model", "schema", "db", "migration", "prisma", "sql"]): return "data or persistence"
    if any(t in p for t in ["config", "settings", "env", "docker", "compose", "yaml", "toml"]): return "configuration"
    return "general code or assets"


def build_areas(files: list[FileInfo]) -> dict[str, dict[str, object]]:
    grouped: dict[str, list[FileInfo]] = defaultdict(list)
    for f in files: grouped[f.top_level].append(f)
    areas: dict[str, dict[str, object]] = {}
    for top, group in sorted(grouped.items()):
        exts = Counter(f.ext or "[no extension]" for f in group)
        label_votes = Counter(infer_area_label(g.path) for g in group[:40])
        areas[top] = {"file_count": len(group), "common_extensions": [ext for ext, _ in exts.most_common(6)], "inferred_role": label_votes.most_common(1)[0][0] if label_votes else "unknown", "sample_paths": [g.path for g in group[:8]]}
    return areas


def extract_symbols_from_text(path: str, text: str) -> list[str]:
    ext = Path(path).suffix.lower(); lines = text.splitlines(); symbols: list[str] = []; patterns: list[re.Pattern[str]] = []
    if ext == ".py": patterns = [re.compile(r"^class\s+([A-Za-z_][A-Za-z0-9_]*)"), re.compile(r"^def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")]
    elif ext in JS_TS_EXTENSIONS: patterns = [re.compile(r"^(?:export\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)"), re.compile(r"^(?:export\s+)?function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("), re.compile(r"^(?:export\s+)?const\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:async\s*)?\("), re.compile(r"^(?:export\s+)?const\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:async\s*)?[A-Za-z_][A-Za-z0-9_]*\s*=>")]
    elif ext == ".go": patterns = [re.compile(r"^type\s+([A-Za-z_][A-Za-z0-9_]*)\s+struct"), re.compile(r"^func\s+(?:\([^)]+\)\s*)?([A-Za-z_][A-Za-z0-9_]*)\s*\(")]
    elif ext in {".java", ".kt", ".kts", ".cs", ".php", ".rb", ".rs", ".swift"}: patterns = [re.compile(r"^(?:public\s+|private\s+|protected\s+|internal\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)"), re.compile(r"^(?:public\s+|private\s+|protected\s+|internal\s+)?(?:static\s+)?(?:fn|func|def|void|int|bool|String|Task|Result|async\s+fn)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")]
    route_patterns = [re.compile(r"\b(app|get|post|put|patch|delete|router)\.(get|post|put|patch|delete)\s*\(\s*['\"]([^'\"]+)['\"]"), re.compile(r"path\s*[:=]\s*['\"]([^'\"]+)['\"]")]
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("//"): continue
        for pat in patterns:
            m = pat.search(line)
            if m: symbols.append(m.group(1)); break
        for pat in route_patterns:
            m = pat.search(line)
            if m:
                value = m.group(m.lastindex or 1)
                if value.startswith("/"): symbols.append(f"route {value}")
        if len(symbols) >= MAX_SYMBOLS_PER_FILE: break
    out: list[str] = []
    seen = set()
    for s in symbols:
        if s not in seen: seen.add(s); out.append(s)
    return out[:MAX_SYMBOLS_PER_FILE]


def build_symbol_index(root: Path, files: list[FileInfo]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for f in files:
        if f.size > MAX_TEXT_FILE_BYTES or f.ext.lower() not in CODE_EXTENSIONS: continue
        text = load_text(root / f.path)
        if text:
            symbols = extract_symbols_from_text(f.path, text)
            if symbols: out[f.path] = symbols
    return out


def build_token_counts(root: Path, files: list[FileInfo]) -> tuple[list[tuple[str, int]], list[tuple[str, int]], dict[str, int]]:
    by_file: list[tuple[str, int]] = []; by_dir: Counter[str] = Counter(); token_map: dict[str, int] = {}
    for f in files:
        tokens = estimate_tokens_for_file(root, f)
        token_map[f.path] = tokens
        by_file.append((f.path, tokens))
        parts = f.path.split("/")
        for i in range(1, len(parts)): by_dir["/".join(parts[:i])] += tokens
        by_dir["."] += tokens
    by_file.sort(key=lambda x: (-x[1], x[0]))
    return by_file[:MAX_TOKEN_ROWS], sorted(by_dir.items(), key=lambda x: (-x[1], x[0]))[:MAX_TOKEN_ROWS], token_map


def build_task_routing(files: list[FileInfo], symbol_index: dict[str, list[str]], areas: dict[str, dict[str, object]]) -> dict[str, list[str]]:
    hits: dict[str, Counter[str]] = defaultdict(Counter)
    for top in areas:
        key = top.lower().replace("_", "-")
        if key not in TASK_STOPWORDS and len(key) >= 3: hits[key][f"{top}/"] += 3
    for f in files:
        path = f.path.lower()
        for t in set(tokenize(path)):
            if t in TASK_STOPWORDS: continue
            weight = 3 if any(mark in t for mark in ["auth", "billing", "payment", "invoice", "login", "user", "account", "profile", "admin", "search", "cart", "order", "checkout", "notification", "email", "sms", "chat", "message", "onboarding", "settings", "report", "analytics", "schema", "migration", "worker", "queue"]) else 1
            hits[t][f.path] += weight
        for sym in symbol_index.get(f.path, [])[:10]:
            for t in tokenize(sym):
                if t not in TASK_STOPWORDS: hits[t][f.path] += 1
    out: dict[str, list[str]] = {}
    for key, counter in hits.items():
        ranked = [path for path, _ in counter.most_common(8)]
        if ranked: out[key] = ranked
    return dict(sorted(out.items())[:MAX_ROUTING_HINTS])


def collect_git_hotspots(root: Path, limit: int = 250) -> dict[str, object]:
    try:
        proc = subprocess.run(["git", "-C", str(root), "log", f"-n{limit}", "--name-only", "--pretty=format:__COMMIT__"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=False)
    except Exception:
        return {"available": False, "reason": "git not available", "top_files": [], "pairs_map": {}}
    if proc.returncode != 0 or not proc.stdout.strip():
        return {"available": False, "reason": "git log unavailable", "top_files": [], "pairs_map": {}}
    file_counts: Counter[str] = Counter(); cochange: Counter[tuple[str, str]] = Counter(); current_files: set[str] = set()
    for raw in proc.stdout.splitlines():
        line = raw.strip()
        if not line: continue
        if line == "__COMMIT__":
            ordered = sorted(current_files)
            for i in range(len(ordered)):
                for j in range(i + 1, len(ordered)): cochange[(ordered[i], ordered[j])] += 1
            current_files = set(); continue
        current_files.add(line); file_counts[line] += 1
    pairs_map: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for (a, b), count in cochange.items():
        pairs_map[a].append((b, count)); pairs_map[b].append((a, count))
    for k in pairs_map: pairs_map[k] = sorted(pairs_map[k], key=lambda x: (-x[1], x[0]))[:10]
    return {"available": True, "top_files": file_counts.most_common(30), "top_pairs": [{"a": a, "b": b, "count": count} for (a, b), count in sorted(cochange.items(), key=lambda x: (-x[1], x[0]))[:20]], "pairs_map": dict(pairs_map)}


def resolve_python_relative_import(current_path: str, module: str, level: int, root: Path) -> list[str]:
    base = Path(current_path).parent
    for _ in range(max(0, level - 1)): base = base.parent
    candidates: list[Path] = []
    if module:
        module_path = Path(*module.split("."))
        candidates.extend([base / f"{module_path}.py", base / module_path / "__init__.py"])
    else:
        candidates.append(base / "__init__.py")
    return [p.as_posix() for p in candidates if (root / p).exists()]


def resolve_js_import(current_path: str, import_path: str, root: Path) -> list[str]:
    if not import_path.startswith((".", "/")): return []
    base = (Path(current_path).parent / import_path).as_posix() if import_path.startswith(".") else import_path.lstrip("/")
    raw = Path(base); candidates = [raw]
    if raw.suffix: candidates.extend([raw.with_suffix(s) for s in JS_TS_EXTENSIONS])
    else:
        for ext in [".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".json"]: candidates.append(Path(str(raw) + ext))
        for ext in [".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"]: candidates.append(raw / f"index{ext}")
    out: list[str] = []
    for c in candidates:
        p = c.as_posix().lstrip("/")
        if (root / p).exists() and p not in out: out.append(p)
    return out


def build_import_graph(root: Path, files: list[FileInfo]) -> dict[str, object]:
    file_set = {f.path for f in files}
    imports_by_file: dict[str, list[str]] = defaultdict(list)
    unresolved: dict[str, list[str]] = defaultdict(list)
    for f in files:
        if f.ext not in CODE_EXTENSIONS: continue
        text = load_text(root / f.path)
        if not text: continue
        found: set[str] = set(); unresolved_local: set[str] = set()
        if f.ext == ".py":
            for m in re.finditer(r"^\s*from\s+(\.+)([A-Za-z0-9_\.]+)?\s+import\s+", text, re.MULTILINE):
                for p in resolve_python_relative_import(f.path, m.group(2) or "", len(m.group(1)), root):
                    if p in file_set: found.add(p)
            for m in re.finditer(r"^\s*from\s+([A-Za-z0-9_\.]+)\s+import\s+", text, re.MULTILINE):
                mod = m.group(1)
                for p in [Path(*mod.split(".")).with_suffix(".py").as_posix(), (Path(*mod.split(".")) / "__init__.py").as_posix()]:
                    if p in file_set: found.add(p)
            for m in re.finditer(r"^\s*import\s+([A-Za-z0-9_\.]+)", text, re.MULTILINE):
                mod = m.group(1)
                for p in [Path(*mod.split(".")).with_suffix(".py").as_posix(), (Path(*mod.split(".")) / "__init__.py").as_posix()]:
                    if p in file_set: found.add(p)
        elif f.ext in JS_TS_EXTENSIONS:
            for pat in [r"import\s+(?:[^\n]*?from\s+)?['\"]([^'\"]+)['\"]", r"require\(\s*['\"]([^'\"]+)['\"]\s*\)", r"export\s+\*\s+from\s+['\"]([^'\"]+)['\"]"]:
                for m in re.finditer(pat, text):
                    target = m.group(1)
                    resolved = resolve_js_import(f.path, target, root)
                    if resolved:
                        for p in resolved:
                            if p in file_set: found.add(p)
                    elif target.startswith((".", "/")):
                        unresolved_local.add(target)
        imports_by_file[f.path] = sorted(found)
        unresolved[f.path] = sorted(unresolved_local)
    reverse: dict[str, list[str]] = defaultdict(list)
    for src, targets in imports_by_file.items():
        for dst in targets: reverse[dst].append(src)
    return {"imports_by_file": dict(imports_by_file), "reverse_imports": {k: sorted(v) for k, v in reverse.items()}, "unresolved": dict(unresolved)}


def render_tree(files: list[FileInfo]) -> str:
    tree: dict = {}
    for f in files:
        node = tree
        for part in f.path.split("/"): node = node.setdefault(part, {})
    lines: list[str] = []
    def walk(node: dict, prefix: str = "") -> None:
        for i, key in enumerate(sorted(node.keys())):
            if len(lines) >= MAX_TREE_LINES: return
            connector = "└── " if i == len(node) - 1 else "├── "
            lines.append(prefix + connector + key)
            walk(node[key], prefix + ("    " if i == len(node) - 1 else "│   "))
    walk(tree)
    if len(lines) >= MAX_TREE_LINES: lines.append("… tree truncated …")
    return "\n".join(lines)


def score_query_against_repo(query: str, files: list[FileInfo], symbol_index: dict[str, list[str]], token_map: dict[str, int], important_files: list[str], entrypoints: list[str], areas: dict[str, dict[str, object]], task_routing: dict[str, list[str]], import_graph: dict[str, object], git_hotspots: dict[str, object]) -> tuple[list[dict[str, object]], list[str]]:
    q_tokens = [t for t in tokenize(query) if t not in TASK_STOPWORDS]
    if not q_tokens: return [], []
    q_counter = Counter(q_tokens)
    imports_by_file = import_graph.get("imports_by_file", {})
    reverse_imports = import_graph.get("reverse_imports", {})
    hotspot_counts = dict(git_hotspots.get("top_files", [])) if git_hotspots.get("available") else {}
    cochange_map = git_hotspots.get("pairs_map", {}) if git_hotspots.get("available") else {}
    scores: dict[str, float] = defaultdict(float)
    reasons: dict[str, list[str]] = defaultdict(list)
    area_lookup = {name.lower(): name for name in areas}
    def bump(path: str, points: float, reason: str) -> None:
        scores[path] += points
        if len(reasons[path]) < 8: reasons[path].append(reason)
    for f in files:
        path_tokens = set(tokenize(f.path)); base = Path(f.path).name.lower(); top = f.top_level.lower()
        symbol_tokens = Counter(tok for sym in symbol_index.get(f.path, []) for tok in tokenize(sym))
        for q, count in q_counter.items():
            if q in path_tokens: bump(f.path, 8.0 * count, f"path token '{q}'")
            if q in base: bump(f.path, 6.0 * count, f"filename contains '{q}'")
            if q == top: bump(f.path, 6.0 * count, f"top-level area '{q}'")
            if q in symbol_tokens: bump(f.path, min(10.0, 3.0 + 1.5 * symbol_tokens[q]) * count, f"symbol match '{q}'")
            if q in area_lookup and f.top_level == area_lookup[q]: bump(f.path, 4.0 * count, f"area match '{q}'")
            if q in task_routing and f.path in task_routing[q]: bump(f.path, max(1.0, 7.0 - task_routing[q].index(f.path)) * count, f"routing hint '{q}'")
            if q in infer_area_label(f.path): bump(f.path, 2.0 * count, f"role hint '{q}'")
        if f.path in important_files: bump(f.path, 1.5, "important file")
        if f.path in entrypoints: bump(f.path, 1.5, "entrypoint hint")
        if f.path in hotspot_counts: bump(f.path, min(4.0, math.log2(hotspot_counts[f.path] + 1)), "recent hotspot")
    seed_paths = [p for p, score in sorted(scores.items(), key=lambda x: (-x[1], x[0]))[:20] if score > 0]
    for path in seed_paths:
        for neighbor in imports_by_file.get(path, [])[:12]: bump(neighbor, scores[path] * 0.18, f"import neighbor of {path}")
        for neighbor in reverse_imports.get(path, [])[:12]: bump(neighbor, scores[path] * 0.22, f"referenced by {path}")
        for neighbor, count in cochange_map.get(path, [])[:8]: bump(neighbor, min(4.0, 0.8 + count * 0.35), f"co-change with {path}")
    ranked = []
    for f in files:
        raw = scores.get(f.path, 0.0)
        if raw <= 0: continue
        penalty = min(6.0, token_map.get(f.path, max(1, f.size // 4)) / 2400.0)
        final = raw - penalty
        ranked.append({"path": f.path, "score": round(final, 3), "raw_score": round(raw, 3), "estimated_tokens": token_map.get(f.path, 0), "reasons": reasons.get(f.path, [])})
    ranked.sort(key=lambda x: (-x["score"], x["estimated_tokens"], x["path"]))
    return ranked[:MAX_QUERY_RESULTS], q_tokens


def write_markdown(path: Path, content: str) -> None:
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def build_pack(root: Path, route_query: str | None = None) -> dict[str, object]:
    out_dir = root / ".claude" / "project-context"; out_dir.mkdir(parents=True, exist_ok=True)
    files = walk_files(root); stack = detect_stack(root, files); commands = extract_commands(root)
    important_files = likely_important_files(files); entrypoints = likely_entrypoints(files); areas = build_areas(files)
    symbol_index = build_symbol_index(root, files); token_files, token_dirs, token_map = build_token_counts(root, files)
    task_routing = build_task_routing(files, symbol_index, areas); git_hotspots = collect_git_hotspots(root)
    import_graph = build_import_graph(root, files); tree = render_tree(files); fingerprint = compute_fingerprint(files)
    ext_counts = Counter(f.ext or "[no extension]" for f in files); top_level_counts = Counter(f.top_level for f in files); total_bytes = sum(f.size for f in files)
    manifest = {"generated_at_utc": utc_now_iso(), "root": str(root), "file_count": len(files), "total_bytes": total_bytes, "top_level_folders": top_level_counts.most_common(25), "extension_counts": ext_counts.most_common(25), "stack": stack, "important_files_count": len(important_files), "entrypoints_count": len(entrypoints), "symbol_index_files": len(symbol_index), "fingerprint": fingerprint, "supports_check_stale": True, "supports_route_query": True, "supports_import_graph": True}
    overview = f"# Project Overview\n\nGenerated: {manifest['generated_at_utc']}\nRoot: `{root}`\n\n## Repo shape\n\n- Total files considered: **{len(files)}**\n- Approx total size considered: **{total_bytes:,} bytes**\n- Most common extensions: {', '.join(f'`{ext}` ({count})' for ext, count in ext_counts.most_common(10))}\n- Largest top-level areas: {', '.join(f'`{name}` ({count})' for name, count in top_level_counts.most_common(10))}\n\n## Detected stack\n\n- Runtime/platforms: {', '.join(stack.get('runtime', []) or ['unknown'])}\n- Frameworks: {', '.join(stack.get('frameworks', []) or ['none confidently detected'])}\n- Tooling: {', '.join(stack.get('tooling', []) or ['none confidently detected'])}\n\n## Most likely first-read files\n\n" + "\n".join(f"- `{p}`" for p in important_files[:20]) + "\n\n## V3 notes\n\n- This file is deterministic and heuristic-based.\n- V3 adds an import graph, query-ranked context selection, token concentration, change hotspots, and a staleness fingerprint.\n- Use `QUERY_CONTEXT.md`, `TASK_ROUTING.md`, `IMPORT_GRAPH.md`, and `TOKEN_COUNTS.md` to reduce blind repo-wide search.\n"
    write_markdown(out_dir / "OVERVIEW.md", overview)
    write_markdown(out_dir / "STACK.md", "# Stack Detection\n\n## Runtime/platforms\n\n" + "\n".join(f"- {item}" for item in (stack.get("runtime") or ["unknown"])) + "\n\n## Frameworks and libraries\n\n" + "\n".join(f"- {item}" for item in (stack.get("frameworks") or ["none confidently detected"])) + "\n\n## Tooling\n\n" + "\n".join(f"- {item}" for item in (stack.get("tooling") or ["none confidently detected"])) + "\n\n## Language hints\n\n" + "\n".join(f"- `{ext}`: {count} files" for ext, count in ext_counts.most_common(15)) + "\n")
    write_markdown(out_dir / "COMMANDS.md", "# Commands\n\nThese commands were extracted from real project files when possible.\n\n" + ("\n".join(f"- `{source}` · **{name}** → `{cmd}`" for source, name, cmd in commands) or "- No commands extracted confidently.") + "\n")
    write_markdown(out_dir / "ENTRYPOINTS.md", "# Likely Entrypoints and Key Config\n\nThese are probable runtime starts, route surfaces, or configuration anchors.\n\n" + ("\n".join(f"- `{p}`" for p in entrypoints) or "- No clear entrypoints detected.") + "\n")
    area_lines = ["# Top-Level Areas", ""]
    for name, meta in areas.items():
        area_lines += [f"## `{name}`", f"- Inferred role: **{meta['inferred_role']}**", f"- File count: **{meta['file_count']}**", f"- Common extensions: {', '.join(f'`{x}`' for x in meta['common_extensions'])}", "- Sample paths:"] + [f"  - `{p}`" for p in meta["sample_paths"]] + [""]
    write_markdown(out_dir / "AREAS.md", "\n".join(area_lines))
    write_markdown(out_dir / "IMPORTANT_FILES.md", "# Important Files\n\n" + "\n".join(f"- `{p}`" for p in important_files))
    symbol_lines = ["# Symbol Index", "", "Best-effort top-level symbols and route hints extracted from source files.", ""]
    for path, symbols in sorted(symbol_index.items()): symbol_lines += [f"## `{path}`"] + [f"- `{sym}`" for sym in symbols] + [""]
    if len(symbol_lines) <= 4: symbol_lines.append("No symbols extracted confidently.")
    write_markdown(out_dir / "SYMBOL_INDEX.md", "\n".join(symbol_lines))
    token_lines = ["# Token Counts", "", "Approximate token concentration to help avoid blowing context on the wrong files.", "", "## Heaviest directories", ""] + [f"- `{path}` → ~{tokens:,} tokens" for path, tokens in token_dirs[:30]] + ["", "## Heaviest files", ""] + [f"- `{path}` → ~{tokens:,} tokens" for path, tokens in token_files[:40]]
    write_markdown(out_dir / "TOKEN_COUNTS.md", "\n".join(token_lines))
    routing_lines = ["# Task Routing", "", "Use this as a first-pass domain map before broad search.", "", "## Suggested domains", ""]
    if not task_routing: routing_lines.append("- No strong routing hints extracted.")
    else:
        for domain, paths in task_routing.items(): routing_lines += [f"## `{domain}`"] + [f"- `{path}`" for path in paths] + [""]
    routing_lines += ["## How to use this", "", "1. Match the user's request to one or more domains above.", "2. Search only those folders/files first.", "3. Expand scope only if the first pass is weak or contradictory.", "4. For an exact task, run `--route-query` to rank likely files dynamically."]
    write_markdown(out_dir / "TASK_ROUTING.md", "\n".join(routing_lines))
    hotspot_lines = ["# Change Hotspots", "", "Git-derived hints about files that change often and files that often change together.", ""]
    if not git_hotspots.get("available"): hotspot_lines.append(f"- Hotspot data unavailable: {git_hotspots.get('reason', 'unknown reason')}")
    else:
        hotspot_lines += ["## Frequently changed files", ""] + [f"- `{path}` → {count} recent commits" for path, count in git_hotspots["top_files"]] + ["", "## Files that often change together", ""] + [f"- `{row['a']}` + `{row['b']}` → {row['count']} co-changes" for row in git_hotspots["top_pairs"]]
    write_markdown(out_dir / "CHANGE_HOTSPOTS.md", "\n".join(hotspot_lines))
    imports_by_file = import_graph["imports_by_file"]; reverse_imports = import_graph["reverse_imports"]
    degree_rows = []
    for path in sorted(set(imports_by_file) | set(reverse_imports)): degree_rows.append((len(imports_by_file.get(path, [])) + len(reverse_imports.get(path, [])), len(reverse_imports.get(path, [])), len(imports_by_file.get(path, [])), path))
    import_lines = ["# Import Graph", "", "Local import/reference edges extracted from source files where possible.", "", "## Most connected files", ""] + [f"- `{path}` → {in_deg} inbound, {out_deg} outbound" for _, in_deg, out_deg, path in sorted(degree_rows, key=lambda x: (-x[0], x[3]))[:40]] + ["", "## Sample edges", ""]
    shown = 0
    for src in sorted(imports_by_file):
        for dst in imports_by_file[src][:5]:
            import_lines.append(f"- `{src}` → `{dst}`"); shown += 1
            if shown >= 60: break
        if shown >= 60: break
    write_markdown(out_dir / "IMPORT_GRAPH.md", "\n".join(import_lines))
    write_markdown(out_dir / "STALENESS.md", "# Staleness\n\n- Generated at: `{}`\n- Fingerprint: `{}`\n\n## Check command\n\n```bash\npython scripts/build_context_pack_v3.py . --check-stale\n```\n".format(manifest["generated_at_utc"], fingerprint))
    if route_query:
        ranked, q_tokens = score_query_against_repo(route_query, files, symbol_index, token_map, important_files, entrypoints, areas, task_routing, import_graph, git_hotspots)
        query_lines = ["# Query Context", "", f"Query: `{route_query}`", f"Tokens: `{', '.join(q_tokens)}`", "", "## Ranked files to read first", ""]
        if not ranked: query_lines.append("- No strong candidates. Fall back to `TASK_ROUTING.md`, then scoped search.")
        else:
            for row in ranked[:20]: query_lines += [f"## `{row['path']}`", f"- score: **{row['score']}**", f"- estimated tokens: **~{row['estimated_tokens']:,}**", "- reasons:"] + [f"  - {reason}" for reason in row['reasons'][:6]] + [""]
            query_lines += ["## How to use this", "", "1. Read the top 3–8 files first.", "2. Add import-graph neighbors for any file that appears central.", "3. Only then run scoped search if the hypothesis is still weak."]
        write_markdown(out_dir / "QUERY_CONTEXT.md", "\n".join(query_lines))
        (out_dir / "QUERY_RESULTS.json").write_text(json.dumps({"query": route_query, "tokens": q_tokens, "ranked": ranked}, indent=2), encoding="utf-8")
    (out_dir / "DIRECTORY_TREE.txt").write_text(tree + "\n", encoding="utf-8")
    (out_dir / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    with (out_dir / "FILES.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f); writer.writerow(["path", "extension", "size_bytes", "top_level"])
        for row in files: writer.writerow([row.path, row.ext, row.size, row.top_level])
    return manifest


def check_stale(root: Path) -> int:
    manifest_path = root / ".claude" / "project-context" / "MANIFEST.json"
    if not manifest_path.exists(): print("STALE: manifest missing"); return 2
    try: manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception: print("STALE: manifest unreadable"); return 2
    current = compute_fingerprint(walk_files(root)); old = manifest.get("fingerprint")
    if old == current: print("OK: project context pack appears current"); return 0
    print("STALE: fingerprint changed"); print(f"old={old}"); print(f"new={current}"); return 1


def main() -> int:
    raw_args = sys.argv[1:]; non_flags: list[str] = []; route_query: str | None = None; i = 0
    while i < len(raw_args):
        arg = raw_args[i]
        if arg == "--route-query" and i + 1 < len(raw_args): route_query = raw_args[i + 1]; i += 2; continue
        if not arg.startswith("--"): non_flags.append(arg)
        i += 1
    flags = {a for a in raw_args if a.startswith("--")}
    root = Path(non_flags[0]).resolve() if non_flags else Path.cwd().resolve()
    if "--check-stale" in flags: return check_stale(root)
    manifest = build_pack(root, route_query=route_query)
    print(f"Wrote project context pack to {root / '.claude' / 'project-context'}")
    print(f"Fingerprint: {manifest['fingerprint']}")
    if route_query: print(f"Query context written for: {route_query}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
