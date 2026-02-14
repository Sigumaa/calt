#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
PROGRESS_FILE="$ROOT/.codex/PLAN_PROGRESS.md"

fail() {
  echo "plan-guard: $1" >&2
  exit 1
}

required_files=(
  "AGENTS.md"
  ".codex/PROJECT_PLAN.md"
  ".codex/PLAN_PROGRESS.md"
  ".codex/STARTUP_CHECKLIST.md"
)

for f in "${required_files[@]}"; do
  if [[ ! -f "$ROOT/$f" ]]; then
    fail "required file is missing: $f"
  fi
done

needs_progress_update=false
progress_staged=false
enforce_staging_guard=false

normalize_path() {
  local p="$1"
  p="${p#$ROOT/}"
  p="${p#./}"
  echo "$p"
}

STAGED_FILES="$(git diff --cached --name-only)"
if [[ -n "$STAGED_FILES" ]]; then
  enforce_staging_guard=true
fi

if [[ "$enforce_staging_guard" == "true" ]]; then
  while IFS= read -r raw; do
    f="$(normalize_path "$raw")"
    [[ -z "$f" || "$f" == "." ]] && continue
    if [[ "${PLAN_GUARD_DEBUG:-0}" == "1" ]]; then
      echo "plan-guard debug: staged raw='$raw' normalized='$f'" >&2
    fi

    if [[ "$f" == ".codex/PLAN_PROGRESS.md" ]]; then
      progress_staged=true
    fi

    case "$f" in
      .codex/*|AGENTS.md|README.md|README.MD|.pre-commit-config.yaml|scripts/precommit/plan_guard.sh|tests/test_plan_guard.sh|.gitignore)
        ;;
      *)
        needs_progress_update=true
        ;;
    esac
  done <<< "$STAGED_FILES"
fi

if [[ "${PLAN_GUARD_DEBUG:-0}" == "1" ]]; then
  echo "plan-guard debug: enforce_staging_guard=$enforce_staging_guard needs_progress_update=$needs_progress_update progress_staged=$progress_staged" >&2
fi

if [[ "$enforce_staging_guard" == "true" && "$needs_progress_update" == "true" && "$progress_staged" == "false" ]]; then
  fail "non-plan changes require staging .codex/PLAN_PROGRESS.md"
fi

grep -Eq '^- 対象フェーズ:[[:space:]]*[^[:space:]]+' "$PROGRESS_FILE" || fail "fill 対象フェーズ in .codex/PLAN_PROGRESS.md"
grep -Eq '^- 対象項目:[[:space:]]*[^[:space:]]+' "$PROGRESS_FILE" || fail "fill 対象項目 in .codex/PLAN_PROGRESS.md"
grep -Eq '^- 担当日時:[[:space:]]*[^[:space:]]+' "$PROGRESS_FILE" || fail "fill 担当日時 in .codex/PLAN_PROGRESS.md"
grep -Eq '^- [0-9]{4}-[0-9]{2}-[0-9]{2}:[[:space:]]*[^[:space:]]+' "$PROGRESS_FILE" || fail "add 実施ログ with date and message"
grep -Eq '^1\.[[:space:]]+[^[:space:]]+' "$PROGRESS_FILE" || fail "fill 次アクション 1"
grep -Eq '^2\.[[:space:]]+[^[:space:]]+' "$PROGRESS_FILE" || fail "fill 次アクション 2"
grep -Eq '^3\.[[:space:]]+[^[:space:]]+' "$PROGRESS_FILE" || fail "fill 次アクション 3"

exit 0
