# PLAN_PROGRESS

## 現在の実施対象
- 対象フェーズ: フェーズ2
- 対象項目: Tool Runtime最小統合（step execute連携・events/runs記録・artifact保存）
- 担当日時: 2026-02-15 12:30

## フェーズ進捗
- [x] フェーズ1: 基盤（モデル/状態遷移/SQLite/API）
- [ ] フェーズ2: 実行（Tool Registry/6ツール/二相適用/Artifact）
- [ ] フェーズ3: クライアント（CLI/Discord 8操作）
- [ ] フェーズ4: 品質（unit/integration/e2e/ドキュメント）

## 受け入れ基準チェック
- [x] Plan未承認またはStep未承認で実行不可
- [x] 全ツール実行がイベントとして追跡可能
- [ ] previewなしでapply不可
- [x] 失敗時は自動停止し続行しない
- [x] FTS検索で実行ログを検索可能
- [ ] DiscordとCLIから同一sessionを操作可能
- [ ] E2E 2本が通過

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

## 次アクション（最大3つ）
1. previewなしapply拒否をruntimeレイヤで強制し、受け入れ基準を完了に更新する
2. CLIとDiscordから同一sessionを操作する結合経路を実装・検証する
3. E2E 2本を追加して受け入れ基準を完了する
