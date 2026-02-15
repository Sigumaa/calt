# PLAN_PROGRESS

## 現在の実施対象
- 対象フェーズ: フェーズ4
- 対象項目: E2E 2本追加と完了処理
- 担当日時: 2026-02-15 14:20

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

## 次アクション（最大3つ）
1. MVP完了判定を確定し、必要に応じてリリースタグ方針を決める
2. E2E実行をCI導線へ接続するかを判断し、必要なら最小ジョブを追加する
3. ドキュメントの運用手順（ローカル実行・障害時リカバリ）を最終確認する
