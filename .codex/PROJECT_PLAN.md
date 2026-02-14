# ローカルツールコーリング基盤 MVP 実装計画

## 概要
- 目的は、ローカルで安全に `Plan -> Approve -> Execute -> Record` を回す基盤を作ること。
- MVP範囲は `基盤 + Discord最小連携`。
- 前提は `Python 3.12`、`Linux正式対応`、`uv run運用`、`内部APIのみ`。
- Planは手動YAML入力、失敗時の再計画は手動でPlan Versionを追加する。
- 承認モデルは `Plan承認 + 全Step承認`。

## スコープ
### In Scope
- ローカルデーモン（HTTP localhost）
- CLIクライアント
- Discord Bot（8操作）
- Tool Registry（最小6種）
- Step逐次実行エンジン
- 二相適用（preview -> apply）
- SQLiteイベントログ + FTS5 + 統計view
- 監査ログ（source + user_id）
- セッション隔離ワークスペース
- 秘密情報マスク
- E2Eテスト2本（成功系 + 失敗系）

### Out of Scope
- LLMによるPlan自動生成
- 並列実行、自動再試行、自動再計画
- 外部公開API互換保証
- マルチOS正式対応

## アーキテクチャ
- `daemon` が唯一の実行主体。
- `cli` と `discord-bot` は操作のみ担当し、ツール実行権限を持たない。
- `storage` は SQLite + filesystem artifacts。
- `tool runtime` は Permission Profile を必須チェックして実行する。
- `planner` はMVPでは手動YAMLの検証器とする。

## リポジトリ構成
- `src/calt/daemon/`
- `src/calt/cli/`
- `src/calt/discord_bot/`
- `src/calt/core/`
- `src/calt/tools/`
- `src/calt/storage/`
- `tests/unit/`
- `tests/integration/`
- `tests/e2e/`
- `data/sessions/<session_id>/workspace/`
- `data/sessions/<session_id>/artifacts/`

## 内部API
- `POST /api/v1/sessions`
- `GET /api/v1/sessions/{session_id}`
- `POST /api/v1/sessions/{session_id}/plans/import`
- `GET /api/v1/sessions/{session_id}/plans/{version}`
- `POST /api/v1/sessions/{session_id}/plans/{version}/approve`
- `POST /api/v1/sessions/{session_id}/steps/{step_id}/approve`
- `POST /api/v1/sessions/{session_id}/steps/{step_id}/execute`
- `POST /api/v1/sessions/{session_id}/stop`
- `GET /api/v1/sessions/{session_id}/events/search?q=...`
- `GET /api/v1/sessions/{session_id}/artifacts`
- `GET /api/v1/tools`
- `GET /api/v1/tools/{tool_name}/permissions`
- 認証は `Authorization: Bearer <token>` を必須とする。

## Plan YAML スキーマ（正本）
```yaml
version: 1
session_goal: "string"
plan_title: "string"
steps:
  - id: "step_001"
    title: "string"
    tool: "read_file | list_dir | run_shell_readonly | write_file_preview | write_file_apply | apply_patch"
    inputs: {}
    risk: "low | medium | high"
    preconditions: ["string"]
    postconditions: ["string"]
    expected_observation: "string"
    verify:
      type: "exit_code | regex | jsonpath | artifact_exists"
      expr: "string"
    timeout_sec: 30
```

## 標準Toolセット（MVP）
- `read_file`
- `list_dir`
- `run_shell_readonly`
- `write_file_preview`
- `write_file_apply`
- `apply_patch`（`mode=preview|apply`）

### `run_shell_readonly` allowlist
- `ls`
- `cat`
- `rg`
- `find`
- `git status`
- `git diff`
- `python -m pytest -q`

## 実行エンジン仕様
- Stepは逐次実行のみ。
- 状態遷移は `pending -> awaiting_plan_approval -> awaiting_step_approval -> running -> succeeded|failed|cancelled|skipped`。
- 全Stepで承認必須。
- 失敗時は即停止し、`needs_replan` に遷移。
- 再計画は手動でPlan Versionを追加して再承認。
- タイムアウトは `Tool 30秒`、`Step 120秒`。

## セキュリティ仕様
- ツール経由の外向きネットワークはMVPで禁止。
- 書き込み対象は `data/sessions/<id>/workspace` のみ。
- 読み取りも原則同ワークスペース内。
- Discord認可は許可ユーザーID固定。
- 秘密情報は保存前に `***REDACTED***` へマスク。
- キー名パターン例: `(?i).*(token|key|secret|password).*`

## データ設計（SQLite）
### Tables
- `sessions`
- `plans`
- `steps`
- `runs`
- `events`（append-only）
- `artifacts`
- `approvals`
- `tool_registry`

### FTS5
- `events_fts`（event summary + redacted payload text）

### Views
- `v_run_success_rate_by_tool`
- `v_step_duration_ms_p50_p95`
- `v_session_failure_reasons`

## Discord MVP（8操作）
- `/session_create`
- `/plan_show`
- `/step_approve`
- `/step_execute`
- `/session_stop`
- `/logs_search`
- `/artifacts_list`
- `/tools_permissions`
- UIは `Slash + Button`。
- 監査ログは `source=discord`, `user_id`, `message_id` を保存。

## CLI MVP
- `calt session create`
- `calt plan import`
- `calt plan approve`
- `calt step approve`
- `calt step execute`
- `calt session stop`
- `calt logs search`
- `calt artifacts list`
- `calt tools list`
- `calt tools permissions`

## テスト計画
### Unit
- Plan YAMLバリデーション
- 状態遷移ルール
- Permission Profile評価
- 秘密情報マスク
- Tool入出力モデル

### Integration
- preview/apply二相整合性
- workspace隔離
- append-onlyイベント記録
- FTS5検索ヒット
- 承認必須時の拒否動作

### E2E（必須2本）
1. 成功系: session作成 -> plan取込 -> plan承認 -> 全step承認/実行 -> Discordで状態確認
2. 失敗系: 途中step失敗 -> 即停止 -> `needs_replan` -> 新Plan Version投入 -> 再承認後再開

## 受け入れ基準
- Plan未承認またはStep未承認で実行不可。
- 全ツール実行がイベントとして追跡可能。
- previewなしでapply不可。
- 失敗時は自動停止し続行しない。
- FTS検索で実行ログを検索可能。
- DiscordとCLIから同一sessionを操作可能。
- E2E 2本が通過する。

## 実装フェーズ
1. 基盤: モデル/状態遷移/SQLite/API
2. 実行: Tool Registry/6ツール/二相適用/Artifact
3. クライアント: CLI/Discord 8操作
4. 品質: unit/integration/e2e/ドキュメント
