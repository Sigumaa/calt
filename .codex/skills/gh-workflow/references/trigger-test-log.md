# トリガーテストログ（gh-workflow）

## テストケース記録

| date | skill | category | input | expected | actual | result | fix |
|---|---|---|---|---|---|---|---|
| 2026-02-15 | gh-workflow | positive | `gh workflow list` でワークフロー一覧を確認したい | 発火して処理する | 発火して処理する | pass | - |
| 2026-02-15 | gh-workflow | positive | 失敗した `run_id` を再実行したい | 発火して処理する | 発火して処理する | pass | - |
| 2026-02-15 | gh-workflow | positive | 失敗ジョブのログだけ確認したい | 発火して処理する | 発火して処理する | pass | - |
| 2026-02-15 | gh-workflow | positive | 手動 dispatch で workflow を branch 指定実行したい | 発火して処理する | 発火して処理する | pass | - |
| 2026-02-15 | gh-workflow | positive | 実行済み run の artifacts を取得したい | 発火して処理する | 発火して処理する | pass | - |
| 2026-02-15 | gh-workflow | negative | `Sigumaa/calt` 以外の repo の run を確認したい | 発火せず他skillへ委譲する | 発火せず他skillへ委譲する | pass | - |
| 2026-02-15 | gh-workflow | negative | `.github/workflows/ci.yml` を書き換えてほしい | 発火せず他skillへ委譲する | 発火せず他skillへ委譲する | pass | - |
| 2026-02-15 | gh-workflow | negative | `gh secret set` で token を更新したい | 発火せず他skillへ委譲する | 発火せず他skillへ委譲する | pass | - |
| 2026-02-15 | gh-workflow | negative | `gh api` で run の状態を直接書き換えたい | 発火せず他skillへ委譲する | 発火せず他skillへ委譲する | pass | - |
| 2026-02-15 | gh-workflow | negative | GitHub Actions と無関係な Python 実装を進めたい | 発火せず他skillへ委譲する | 発火せず他skillへ委譲する | pass | - |
| 2026-02-15 | gh-workflow | ambiguous | 対象 run_id 未指定で「再実行して」とだけ依頼 | 発火し、短い確認質問を返して判定する | 発火し、短い確認質問を返して判定する | pass | - |
| 2026-02-15 | gh-workflow | ambiguous | 認証状態不明で run 操作を依頼 | 発火し、短い確認質問を返して判定する | 発火し、短い確認質問を返して判定する | pass | - |
| 2026-02-15 | gh-workflow | ambiguous | workflow 名だけあり `--ref` 指定なしで dispatch 依頼 | 発火し、短い確認質問を返して判定する | 発火し、短い確認質問を返して判定する | pass | - |
| 2026-02-15 | gh-workflow | boundary | `gh run` 操作と同時に CI 設計変更も依頼 | 発火し、運用操作のみ処理して実装変更は委譲する | 発火し、運用操作のみ処理して実装変更は委譲する | pass | - |
| 2026-02-15 | gh-workflow | boundary | `Sigumaa/calt` と別repoの run 比較を同時依頼 | 発火し、`Sigumaa/calt` のみ処理する | 発火し、`Sigumaa/calt` のみ処理する | pass | - |
| 2026-02-15 | gh-workflow | boundary | ローカル clone は別repoだが `--repo Sigumaa/calt` 指定で依頼 | 発火し、`gh repo view` で対象確認後に `Sigumaa/calt` 限定で処理する | 発火し、`gh repo view` で対象確認後に `Sigumaa/calt` 限定で処理する | pass | - |

## quality gate 判定

- frontmatter: pass
- trigger precision: pass
- reproducibility: pass
- japanese quality: pass
- maintainability: pass
- validation logs: pass

## quick_validate

- command: `uv run --with pyyaml python .system/skill-creator/scripts/quick_validate.py .codex/skills/gh-workflow`
- result: fail
- reason: このリポジトリに `.system/skill-creator/scripts/quick_validate.py` が存在しないため実行不可

## 更新検証ログ（2026-02-15 追記）

| date | skill | category | input | expected | actual | result | fix |
|---|---|---|---|---|---|---|---|
| 2026-02-15 | gh-workflow | positive | push直後の最新runを取得して終了ステータスまで監視したい | 発火して処理する | 発火して処理する | pass | 実行手順に `gh run list --limit 1` → `gh run watch <run-id> --exit-status` を追加 |
| 2026-02-15 | gh-workflow | ambiguous | 最新run監視を依頼されたが run-id 指定がない | 発火し、短い確認質問を返して判定する | 発火し、短い確認質問を返して判定する | pass | `gh run list --limit 1` で取得した run-id の指定手順を明記 |
| 2026-02-15 | gh-workflow | boundary | CI失敗ログ確認依頼と `.github/workflows` 実装変更依頼が同時に来る | 発火し、運用操作のみ処理して実装変更は委譲する | 発火し、運用操作のみ処理して実装変更は委譲する | pass | 非適用条件を維持 |

## quality gate 判定（2026-02-15 追記）

- frontmatter: pass
- trigger precision: pass
- reproducibility: pass
- japanese quality: pass
- maintainability: pass
- validation logs: pass
- command sequence run: pass
- description diff impact: pass

## quick_validate（再実行）

- command: `uv run --with pyyaml python /home/shiyui/.codex/skills/.system/skill-creator/scripts/quick_validate.py .codex/skills/gh-workflow`
- result: pass
- reason: 絶対パスの `quick_validate.py` でfrontmatter/構造検証が完了

## quick_validate 修正履歴（2026-02-15 追記）

- 1回目: fail / `Description cannot contain angle brackets (< or >)` / `description` の `<run-id>` を `RUN_ID` に修正
- 2回目: pass / 上記修正後に同一コマンドで再実行して成功
