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
