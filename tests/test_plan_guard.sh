#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
GUARD_SCRIPT="$ROOT_DIR/scripts/precommit/plan_guard.sh"

pass() {
  echo "ok: $1"
}

die() {
  echo "ng: $1" >&2
  exit 1
}

make_repo() {
  local repo
  repo="$(mktemp -d)"
  git -C "$repo" init -q
  mkdir -p "$repo/.codex" "$repo/scripts/precommit" "$repo/tests" "$repo/src"
  cp "$GUARD_SCRIPT" "$repo/scripts/precommit/plan_guard.sh"
  cat > "$repo/AGENTS.md" <<'EOF'
# AGENTS
EOF
  cat > "$repo/.codex/PROJECT_PLAN.md" <<'EOF'
# PLAN
EOF
  cat > "$repo/.codex/STARTUP_CHECKLIST.md" <<'EOF'
# CHECKLIST
EOF
  cat > "$repo/.codex/PLAN_PROGRESS.md" <<'EOF'
# PLAN_PROGRESS

## 現在の実施対象
- 対象フェーズ: フェーズ1
- 対象項目: ガード導入
- 担当日時: 2026-02-14 12:00

## 実施ログ
- 2026-02-14: 初期化

## 次アクション（最大3つ）
1. 追加
2. 実行
3. 確認
EOF
  echo "$repo"
}

run_guard() {
  local repo="$1"
  shift
  (
    cd "$repo"
    bash scripts/precommit/plan_guard.sh "$@"
  )
}

expect_fail() {
  local name="$1"
  shift
  if "$@"; then
    die "$name (expected failure but passed)"
  fi
  pass "$name"
}

expect_pass() {
  local name="$1"
  shift
  if ! "$@"; then
    die "$name (expected pass but failed)"
  fi
  pass "$name"
}

case_requires_progress_staged() {
  local repo
  repo="$(make_repo)"
  echo "print('x')" > "$repo/src/main.py"
  git -C "$repo" add src/main.py
  expect_fail "non-plan change requires PLAN_PROGRESS staging" run_guard "$repo" "src/main.py"
}

case_pass_with_progress_staged() {
  local repo
  repo="$(make_repo)"
  echo "print('x')" > "$repo/src/main.py"
  git -C "$repo" add src/main.py .codex/PLAN_PROGRESS.md
  expect_pass "non-plan change passes when PLAN_PROGRESS is staged together" run_guard "$repo" "src/main.py" ".codex/PLAN_PROGRESS.md"
}

case_missing_required_file() {
  local repo
  repo="$(make_repo)"
  rm -f "$repo/AGENTS.md"
  expect_fail "missing required file should fail" run_guard "$repo" ".codex/PLAN_PROGRESS.md"
}

case_pass_with_absolute_paths() {
  local repo
  repo="$(make_repo)"
  echo "print('x')" > "$repo/src/main.py"
  git -C "$repo" add src/main.py .codex/PLAN_PROGRESS.md
  expect_pass "absolute paths should be normalized" run_guard "$repo" "$repo/src/main.py" "$repo/.codex/PLAN_PROGRESS.md"
}

case_requires_progress_staged
case_pass_with_progress_staged
case_missing_required_file
case_pass_with_absolute_paths
