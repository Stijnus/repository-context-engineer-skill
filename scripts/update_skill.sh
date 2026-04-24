#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Update Repository Context Engineer files in a Claude Code skill install or Codex target repo.

Usage:
  bash scripts/update_skill.sh [options]

Options:
  --mode <claude|codex>   Update mode. Default: claude
  --target <path>         Destination path.
                          Default for claude: ~/.claude/skills/repository-context-engineer
                          Required for codex.
  --source <path>         Source checkout to sync from.
                          Default: the repository containing this script.
  --pull                  Pull the latest changes from origin/<branch> in the source checkout
                          before syncing files.
  --branch <name>         Git branch to pull when --pull is used. Default: main
  --no-backup             Do not back up managed files before overwriting them.
  --help                  Show this help text.

Examples:
  bash scripts/update_skill.sh --pull
  bash scripts/update_skill.sh --pull --target ~/.claude/skills/repository-context-engineer
  bash scripts/update_skill.sh --pull --mode codex --target /path/to/target-repo
EOF
}

die() {
  echo "Error: $*" >&2
  exit 1
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd -P)"

MODE="claude"
SOURCE_DIR="$REPO_ROOT"
TARGET_DIR=""
BRANCH="main"
PULL_SOURCE=0
NO_BACKUP=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      [[ $# -ge 2 ]] || die "--mode requires a value"
      MODE="$2"
      shift 2
      ;;
    --target)
      [[ $# -ge 2 ]] || die "--target requires a value"
      TARGET_DIR="$2"
      shift 2
      ;;
    --source)
      [[ $# -ge 2 ]] || die "--source requires a value"
      SOURCE_DIR="$2"
      shift 2
      ;;
    --branch)
      [[ $# -ge 2 ]] || die "--branch requires a value"
      BRANCH="$2"
      shift 2
      ;;
    --pull)
      PULL_SOURCE=1
      shift
      ;;
    --no-backup)
      NO_BACKUP=1
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      die "Unknown argument: $1"
      ;;
  esac
done

case "$MODE" in
  claude|codex) ;;
  *) die "--mode must be either 'claude' or 'codex'" ;;
esac

SOURCE_DIR="$(cd "$SOURCE_DIR" && pwd -P)"

if [[ -z "$TARGET_DIR" ]]; then
  if [[ "$MODE" == "claude" ]]; then
    TARGET_DIR="$HOME/.claude/skills/repository-context-engineer"
  else
    die "When --mode codex is used, --target is required"
  fi
fi

managed_files=()
case "$MODE" in
  claude)
    managed_files=(
      "SKILL.md"
      "AGENTS.md"
      "README.md"
      "USAGE.md"
      "scripts/build_context_pack.py"
      "scripts/build_context_pack_v3.py"
      "scripts/update_skill.sh"
      "scripts/update_skill.ps1"
      "examples/settings.snippets.jsonc"
    )
    ;;
  codex)
    managed_files=(
      "AGENTS.md"
      "scripts/build_context_pack.py"
      "scripts/build_context_pack_v3.py"
      "scripts/update_skill.sh"
      "scripts/update_skill.ps1"
    )
    ;;
esac

for rel in "${managed_files[@]}"; do
  [[ -e "$SOURCE_DIR/$rel" ]] || die "Managed file is missing from source checkout: $rel"
done

if (( PULL_SOURCE )); then
  git -C "$SOURCE_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "--pull requires --source to be a git checkout"
  git -C "$SOURCE_DIR" fetch origin "$BRANCH"
  current_branch="$(git -C "$SOURCE_DIR" rev-parse --abbrev-ref HEAD)"
  if [[ "$current_branch" != "$BRANCH" ]]; then
    git -C "$SOURCE_DIR" checkout "$BRANCH"
  fi
  git -C "$SOURCE_DIR" pull --ff-only origin "$BRANCH"
fi

same_root=0
if [[ -d "$TARGET_DIR" ]]; then
  target_canon="$(cd "$TARGET_DIR" && pwd -P)"
  if [[ "$SOURCE_DIR" == "$target_canon" ]]; then
    same_root=1
  fi
fi

if (( same_root )); then
  echo "Source and target are the same directory. The checkout is now up to date."
  echo "Restart Claude Code or your Codex session if it is already running."
  exit 0
fi

backup_root=""
if (( ! NO_BACKUP )) && [[ -d "$TARGET_DIR" ]]; then
  existing=0
  for rel in "${managed_files[@]}"; do
    if [[ -e "$TARGET_DIR/$rel" ]]; then
      existing=1
      break
    fi
  done

  if (( existing )); then
    timestamp="$(date +%Y%m%d-%H%M%S)"
    backup_root="$TARGET_DIR/.repository-context-engineer-backups/$timestamp"
    for rel in "${managed_files[@]}"; do
      src="$TARGET_DIR/$rel"
      if [[ -e "$src" ]]; then
        mkdir -p "$(dirname "$backup_root/$rel")"
        cp -R "$src" "$backup_root/$rel"
      fi
    done
  fi
fi

mkdir -p "$TARGET_DIR"
for rel in "${managed_files[@]}"; do
  src="$SOURCE_DIR/$rel"
  dest="$TARGET_DIR/$rel"
  mkdir -p "$(dirname "$dest")"
  cp "$src" "$dest"
done

if [[ -f "$TARGET_DIR/scripts/update_skill.sh" ]]; then
  chmod +x "$TARGET_DIR/scripts/update_skill.sh" 2>/dev/null || true
fi

echo "Updated Repository Context Engineer files in: $TARGET_DIR"
if [[ -n "$backup_root" ]]; then
  echo "Backup written to: $backup_root"
fi

echo "Mode: $MODE"
echo "Source checkout: $SOURCE_DIR"
echo "Restart Claude Code or your Codex session if it is already running."
