#!/usr/bin/env bash
set -euo pipefail

ROOT="."

while (($# > 0)); do
  case "$1" in
    --root)
      if (($# < 2)); then
        echo "ERROR: --root requires a directory path" >&2
        exit 1
      fi
      ROOT="$2"
      shift 2
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

mkdir -p "$ROOT"

create_if_missing() {
  local rel_path="$1"
  local target_path="$ROOT/$rel_path"

  if [ -e "$target_path" ]; then
    cat >/dev/null
    printf "SKIPPED: %s\n" "$rel_path"
    return 0
  fi

  mkdir -p "$(dirname "$target_path")"
  cat >"$target_path"
  printf "CREATED: %s\n" "$rel_path"
}

create_if_missing "AGENTS.md" <<'EOF'
# AGENTS.md

## このリポジトリの運用目的
- このリポジトリでは、実装より先に計画を固定し、計画に沿って実行する。
- 計画の正本は `.codex/PROJECT_PLAN.md` とする。

## 必須ルール
1. 作業開始前に必ず `.codex/PROJECT_PLAN.md` と `.codex/PLAN_PROGRESS.md` を読む。
2. 着手時に対象フェーズと対象項目を明示する。
3. 実装後は `.codex/PLAN_PROGRESS.md` の `実施ログ` と `次アクション` を更新する。
4. 計画変更が必要な場合は `.codex/PROJECT_PLAN.md` と `.codex/PLAN_PROGRESS.md` を同時に更新する。
5. Plan未確認で実装を始めない。
6. コミット前に `pre-commit` を必ず通す。
7. 実装ファイルを変更したコミットでは `.codex/PLAN_PROGRESS.md` の同時更新を必須とする。
8. `.codex/STARTUP_CHECKLIST.md` の `コミット前` 項目を満たしていない場合はコミットしない。

## 完了判定
- 個別作業の完了は `.codex/PLAN_PROGRESS.md` の該当チェック完了で判定する。
- MVP完了は `.codex/PROJECT_PLAN.md` の `受け入れ基準` を満たしたときに判定する。

## 運用ガード
- `pre-commit` で以下を強制する。
- 必須ファイル（`AGENTS.md`, `.codex/PROJECT_PLAN.md`, `.codex/PLAN_PROGRESS.md`, `.codex/STARTUP_CHECKLIST.md`）の存在
- 実装変更時の `.codex/PLAN_PROGRESS.md` 同時更新
- `.codex/PLAN_PROGRESS.md` の必須項目の未記入防止
EOF

create_if_missing ".codex/PROJECT_PLAN.md" <<'EOF'
# PROJECT_PLAN

## 概要
- 目的:
- 背景:
- 制約:

## 実装フェーズ
1. フェーズ1:
2. フェーズ2:
3. フェーズ3:

## 受け入れ基準
- [ ] 受け入れ基準1
- [ ] 受け入れ基準2
- [ ] 受け入れ基準3
EOF

create_if_missing ".codex/PLAN_PROGRESS.md" <<'EOF'
# PLAN_PROGRESS

## 現在の実施対象
- 対象フェーズ:
- 対象項目:
- 担当日時:

## フェーズ進捗
- [ ] フェーズ1
- [ ] フェーズ2
- [ ] フェーズ3

## 受け入れ基準チェック
- [ ] 受け入れ基準1
- [ ] 受け入れ基準2
- [ ] 受け入れ基準3

## 実施ログ
- YYYY-MM-DD: 着手内容を記録

## 次アクション（最大3つ）
1. 次アクション1
2. 次アクション2
3. 次アクション3
EOF

create_if_missing ".codex/STARTUP_CHECKLIST.md" <<'EOF'
# STARTUP_CHECKLIST

## 作業開始前
1. `.codex/PROJECT_PLAN.md` を読む。
2. `.codex/PLAN_PROGRESS.md` の現在地を確認する。
3. 今回触る範囲が計画のどこに当たるかを1行で書く。
4. `.codex/PLAN_PROGRESS.md` の `対象フェーズ/対象項目/担当日時` を記入する。

## 実装前
1. 承認・安全制約に反する操作がないか確認する。
2. 変更対象と非対象を明確化する。
3. 安全プロファイル（strict/dev）の選択確認を行う。

## 実装後
1. `.codex/PLAN_PROGRESS.md` のチェックを更新する。
2. `実施ログ` に結果を追記する。
3. `次アクション` を3つ以内で更新する。

## コミット前
1. `pre-commit run --all-files` を実行し、失敗を解消する。
2. Docker経由の検証を実施（対象変更時）。
3. 実装変更を含む場合、`.codex/PLAN_PROGRESS.md` が同時にステージされていることを確認する。
4. 受け入れ基準に影響する変更なら `.codex/PROJECT_PLAN.md` も更新する。
EOF

create_if_missing ".codex/DOCKER_TESTING.md" <<'EOF'
# DOCKER_TESTING

## 前提
- Docker Engine が利用可能であること。
- Docker Compose が利用可能であること。

## 実行手順
1. `docker compose version` で利用可否を確認する。
2. `bash scripts/docker_test.sh` を実行する。
3. 失敗時はログを保存し、再現条件を `PLAN_PROGRESS` に記録する。
EOF

create_if_missing ".github/workflows/precommit.yml" <<'EOF'
name: pre-commit

on:
  push:
    branches:
      - main
      - master
  pull_request:

jobs:
  pre-commit:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Run pre-commit
        uses: pre-commit/action@v3.0.1
EOF
