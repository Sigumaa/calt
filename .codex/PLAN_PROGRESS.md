# PLAN_PROGRESS

## 現在の実施対象
- 対象フェーズ: フェーズC
- 対象項目: step出力参照展開 + C-2/C-3サンプル追加
- 担当日時: 2026-02-15 19:10

## フェーズ進捗
- [x] フェーズ1: 基盤（モデル/状態遷移/SQLite/API）
- [x] フェーズ2: 実行（Tool Registry/6ツール/二相適用/Artifact）
- [x] フェーズ3: クライアント（CLI/Discord 8操作）
- [x] フェーズ4: 品質（unit/integration/e2e/ドキュメント）

## 受け入れ基準チェック
- [x] Plan未承認またはStep未承認で実行不可
- [x] 全ツール実行がイベントとして追跡可能
- [x] previewなしでapply不可
- [x] 失敗時は自動停止し続行しない
- [x] FTS検索で実行ログを検索可能
- [x] DiscordとCLIから同一sessionを操作可能
- [x] E2E 2本が通過

## 実施ログ
- 2026-02-14: pre-commit設定とplan-guardを追加し、テストケースを作成
- 2026-02-15: pre-commitツールをローカル導入し、フック有効化のセットアップを実施
- 2026-02-15: `pre-commit` と `pre-push` フックを有効化し、CIワークフローを追加
- 2026-02-15: `plan-guard` のpre-commitバッチ実行時の誤判定を修正し、絶対パスケースをテスト追加
- 2026-02-15: `uv` でPythonプロジェクトを初期化し、`ruff` `mypy` `pytest` を開発依存へ追加。最小pytestを追加して実行。
- 2026-02-15: `src/calt/daemon/` を新規追加し、FastAPIベースの内部API（sessions/plans/steps/stop/events/artifacts/tools）を最小実装。
- 2026-02-15: `tests/integration/test_daemon_api.py` を追加し、承認前実行拒否・承認後実行成功・stop・tools取得・plan/events/artifactsを統合テストで固定。
- 2026-02-15: `fastapi` `httpx` `anyio` を依存追加し、`uv run pytest -q` と `pre-commit run --all-files` を通過。
- 2026-02-15: `src/calt/core` `src/calt/storage` `tests/unit` `tests/integration/test_sqlite_storage.py` を点検し、`uv run pytest -q tests/unit tests/integration/test_sqlite_storage.py` 10件成功を確認。
- 2026-02-15: `src/calt/runtime/` を新規作成し、Step実行器を追加。`step execute` から既存tools実行・runs/events記録・artifactファイル保存まで統合。
- 2026-02-15: `events search` をFTS失敗時にLIKEフォールバック対応し、`artifacts list` が実行生成データを返す統合テストを追加。
- 2026-02-15: `src/calt/tools/` と `tests/unit/test_tools_readonly.py` `tests/unit/test_tools_two_phase.py` を取り込み確認し、`uv run pytest -q tests/unit/test_tools_readonly.py tests/unit/test_tools_two_phase.py` 24件成功と `pre-commit run --all-files` 通過を確認。
- 2026-02-15: runtime/daemonにpreview gateを追加し、`write_file_apply` と `apply_patch mode=apply` のpreviewなし実行を拒否。失敗時のruns/events記録と統合テスト（拒否/成功）を追加。
- 2026-02-15: 安全方針に合わせて `tests/integration/test_preview_gate.py` を `tmp_path` 配下の明示 `data_root` へ隔離し、実環境非依存の疑似統合テストとして再実行。
- 2026-02-15: `pyproject.toml` に `project.scripts.calt = "calt.cli:run"` を追加し、CLIエントリポイントを確定。
- 2026-02-15: `tests/integration/test_cli_discord_bridge.py` を追加し、`tmp_path` + in-process daemon でCLIとDiscordサービスが同一sessionを操作できることを統合テストで固定。
- 2026-02-15: Docker検証資料（`.codex/DOCKER_TESTING.md` `Dockerfile` `docker-compose.test.yml` `scripts/docker_test.sh`）を取り込み、検証導線を整備。
- 2026-02-15: `uv run pytest -q` を実行し、77件成功を確認。
- 2026-02-15: `pre-commit run --all-files` を実行し、全フック通過を確認。
- 2026-02-15: `src/calt/daemon/api.py` に failed/cancelled 状態でのstep実行拒否と `needs_replan` 応答項目を追加し、失敗時の即停止と再計画導線を明示。
- 2026-02-15: `tests/e2e/test_end_to_end_flows.py` を追加し、成功系（session作成→plan取込→plan承認→全step承認/実行→ログ/成果物確認）と失敗復旧系（途中失敗→停止→needs_replan相当確認→plan version更新→再承認後再開成功）を固定。
- 2026-02-15: `uv run pytest -q tests/e2e` 2件成功、`uv run pytest -q` 79件成功、`pre-commit run --all-files` 全フック通過を確認。
- 2026-02-15: `.github/workflows/docker-test.yml` を追加し、`pull_request` と `main/master` push で `bash scripts/docker_test.sh` を実行するDockerテストCIを整備。`pre-commit run --all-files` を実行して全フック通過を確認。
- 2026-02-15: `scripts/check_docker_compose.sh` を追加し、`.codex/DOCKER_TESTING.md` にOS別のCompose導入/確認手順を追記。
- 2026-02-15: `scripts/docker_test.sh` と `Dockerfile` を更新し、Dockerテストで `tests/e2e` を含む `tests/unit` `tests/integration` `tests/e2e` を実行する導線に変更。
- 2026-02-15: `.codex/skills/gh-workflow/` を新規作成し、`Sigumaa/calt` 限定の `gh workflow`/`gh run` 運用手順・禁止事項・トリガーテストログを整備。`AGENTS.md` に利用タイミングと非適用条件を追記。
- 2026-02-15: `gh-workflow` skill に push直後監視手順（`gh run list --limit 1` → `gh run watch <run-id> --exit-status`）と quick_validate のグローバル実在パスを追加し、`AGENTS.md` とトリガー検証ログを更新。
- 2026-02-15: `/home/shiyui/.codex/skills/subagent-manager-workflow/` を新規作成し、PM専任の委譲運用手順・禁止事項・品質ゲートとトリガー検証ログを整備。`AGENTS.md` に利用タイミングと非適用条件を追記。
- 2026-02-15: `calt-daemon` エントリポイントを追加し、`create_app` を使う起動引数（db-path/data-root/host/port/reload）と単体テストを整備。
- 2026-02-15: `readme.md` に最短クイックスタートを整備し、`examples/sample_plan.json` と検証テスト `tests/unit/test_sample_plan_json.py` を追加。
- 2026-02-15: `connect_sqlite` でDBファイル親ディレクトリを自動作成するよう修正し、未存在ディレクトリ配下でも接続できる回帰テストを追加。
- 2026-02-15: `src/calt/cli/display.py` を追加し、`session create` `plan import` `step execute` `logs search` を見やすい表示へ更新。`calt guide` と `calt flow run`、関連テスト、`readme.md` を追加更新。
- 2026-02-15: daemon検索のevent_type対応とCLI `quickstart`/`doctor` 導線（README・テスト含む）を統合し、`uv run pytest -q` 92件成功と `pre-commit run --all-files` 通過を確認。
- 2026-02-15: Docker実行時に `/app/examples/sample_plan.json` が参照できないCI失敗へ対応し、`Dockerfile` に `examples/` コピーを追加。
- 2026-02-15: MVP完了後の拡張計画v2を策定し、優先順を安全→CLIとして再起動。
- 2026-02-15: フェーズA-1として `session mode`（`normal`/`dry_run`）をAPI/CLI/DBへ追加し、high-risk stepの `confirm_high_risk` 必須化と dry_run 時の apply 系実行拒否（`write_file_apply`, `apply_patch mode=apply`）を実装。統合/単体テストを更新。
- 2026-02-15: フェーズA-2として `safety_profile`（`strict`/`dev`）をSessionモデル・SQLite・API・CLI・HTTP clientへ追加。`strict` は既存の high-risk confirm と preview gate を維持し、`dev` は当該2制約をスキップするよう `execute_step` を更新。`dry_run` の destructive apply 拒否はプロファイル非依存で維持。関連するunit/integrationテストを追加更新。
- 2026-02-15: フェーズA-3として `src/calt/daemon/docker_env.py` を追加し、destructive apply（`write_file_apply` / `apply_patch mode=apply`）に対して strict 非Docker時は `docker required` で 409 拒否、dev 非Docker時は warning 監査イベント記録のうえ実行継続するガードを `execute_step` に統合。integration/unit テストを追加更新。
- 2026-02-15: フェーズB-1として `calt wizard run` を追加し、`_run_flow_operation` を再利用して `flow run` 同等導線を実装。`plan_file` 未指定時のprompt（既定 `examples/sample_plan.json`）と `goal` 未指定時のprompt（既定 `session_goal`）を追加し、`tests/unit/test_cli.py` と `readme.md` を更新。
- 2026-02-15: `uv run pytest -q tests/unit tests/integration` を実行し 108件成功を確認。`pre-commit run --all-files` を実行し全フック通過を確認。
- 2026-02-15: フェーズB-2として `calt explain <session_id>` と `--json` を追加。`get_session`/`get_plan` で状態を判定し、次アクション提案（plan approve/step approve/step execute/replan/new session）を返す実装と単体テストを追加。`readme.md` に利用例を追記。
- 2026-02-15: `uv run pytest -q tests/unit tests/integration` を実行し 112件成功を確認。`pre-commit run --all-files` を実行し全フック通過を確認。
- 2026-02-15: フェーズC-1として `examples/workspace_overview_plan.json` `examples/search_inspect_plan.json` `examples/preview_only_write_plan.json` を追加し、`tests/unit/test_sample_plan_json.py` を全サンプル検証へ拡張。`readme.md` にサンプルPlan一覧と quickstart/wizard 実行例を追記。
- 2026-02-15: フェーズB-2追補として `wizard run` サマリに plan title/goal を追加し、`explain` に `plan_version` `plan_title` `pending_step_id` `pending_step_status` を追加。`tests/unit/test_cli.py` と `readme.md` を更新。
- 2026-02-15: フェーズBのtoken未設定時UX改善として `src/calt/cli/app.py` と `src/calt/client/http.py` に空token検出を追加。通常コマンドはHTTP呼び出し前に行動可能なエラーを返し、`doctor` は token FAIL とAPI系SKIPを返すよう整理。`tests/unit/test_cli.py` と `tests/unit/test_client_http.py` を更新。
- 2026-02-15: フェーズC-2/C-3として `src/calt/daemon/api.py` に `${steps.<step_id>.output}` / `${steps.<step_id>.output.<field_path>}` のstep入力参照展開を追加し、解決不可参照を 409 で拒否する実装を追加。`tests/integration/test_step_input_references.py` を新規追加し、成功系（applyへ参照展開）と失敗系（409）を固定。
- 2026-02-15: `examples/c2_two_phase_apply_plan.json` と `examples/c3_needs_replan_plan.json` を追加し、`tests/unit/test_sample_plan_json.py` のサンプル検証を拡張。`readme.md` に参照構文と C-2/C-3 実行例を追記。
- 2026-02-15: `readme.md` に `実行ログ例` セクションを追加し、`doctor` / `wizard run` / `explain` / C-2/C-3コマンド列 / token未設定時挙動を追記。
- 2026-02-15: `readme.md` の `## Next Roadmap` セクションで 3件の `（計画中）` を `（実装済み）` に更新。

## 次アクション（最大3つ）
1. C-2/C-3サンプルを使った実行ログ（`events search`）の具体例をREADMEへ追加
2. step参照構文の配列インデックス対応要否を要件として確定
3. `needs_replan` 時の再計画テンプレート例を `examples/` へ追加検討
