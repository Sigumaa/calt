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

## Skills

### Available skills
- gh-workflow: `Sigumaa/calt` リポジトリで GitHub Actions のワークフロー実行状況を `gh workflow` と `gh run` で確認・再実行・監視する運用スキル。CI失敗の原因切り分け、対象ジョブ再実行、実行ログ取得、push直後の最新run監視（`gh run list --limit 1` → `gh run watch RUN_ID --exit-status`）を行う依頼で使用する。典型要求は「workflow一覧を見たい」「runを再実行したい」「失敗ジョブのログを確認したい」。`Sigumaa/calt` 以外のリポジトリ操作、`gh` 未認証環境での実操作、ワークフロー以外の実装作業には使用しない。 (file: `.codex/skills/gh-workflow/SKILL.md`)

### 利用タイミング
- `gh workflow` / `gh run` の一覧確認、失敗run分析、再実行、キャンセル、ログ確認を依頼されたときに使う。
- pushや手動dispatch直後に、最新runを取得して終了ステータスまで監視したいときに使う。
- GitHub Actions の運用オペレーションを、`Sigumaa/calt` 限定で実行するときに使う。

### 非適用条件
- `Sigumaa/calt` 以外のリポジトリを対象にする依頼では使わない。
- `gh auth status` が未認証で、認証前提を満たさない状態のまま実操作する依頼では使わない。
- `.github/workflows` 実装変更、CI設計変更、一般的なGit操作は本skillの対象外とする。
