---
name: gh-workflow
description: Sigumaa/calt リポジトリで GitHub Actions のワークフロー実行状況を `gh workflow` と `gh run` で確認・再実行・監視するための運用スキル。CI失敗の原因切り分け、対象ジョブ再実行、実行ログ取得、失敗通知の一次対応を行う依頼で使用する。典型要求は「workflow一覧を見たい」「runを再実行したい」「失敗ジョブのログを確認したい」。`Sigumaa/calt` 以外のリポジトリ操作、`gh` 未認証環境での実操作、ワークフロー以外の実装作業には使用しない。
---

# GitHub Workflow 運用スキル（Sigumaa/calt 限定）

## Overview
- この skill は `Sigumaa/calt` の GitHub Actions 運用操作に限定して使う。
- 対応範囲は `gh workflow` と `gh run` を使う確認・監視・再実行・ログ確認である。
- `--repo` で他リポジトリを指定する操作は禁止する。

## ワークフロー判定
- 次の依頼なら発火して処理する。
  - workflow 一覧や run 一覧を確認したい
  - 失敗 run のログを見たい
  - 対象 run を rerun / cancel したい
- 次の依頼は発火せず他手順へ委譲する。
  - `Sigumaa/calt` 以外の repository 操作
  - `.github/workflows/*.yml` の実装変更
  - `gh secret` や `gh variable` の管理
- 次の依頼は発火し、短い確認質問を返して判定する。
  - 対象 run_id / workflow 名が未指定
  - 認証状態が不明

## 実行手順
1. 対象リポジトリの固定
```bash
gh repo view --json nameWithOwner -q .nameWithOwner
```
- 結果が `Sigumaa/calt` 以外なら停止し、対象外として返答する。

2. 認証前提の確認
```bash
gh auth status
```
- `github.com` で有効なログインがない場合は実操作を中止する。
- 必要時の案内コマンド:
```bash
gh auth login --web --hostname github.com --git-protocol https
```

3. workflow 定義の確認（`gh workflow`）
```bash
gh workflow list
gh workflow view "<workflow-name-or-id>"
```

4. run 状態の確認（`gh run`）
```bash
gh run list --limit 20
gh run view <run-id>
gh run view <run-id> --log-failed
```

5. run の操作（必要時のみ）
```bash
gh run rerun <run-id>
gh run rerun <run-id> --failed
gh run cancel <run-id>
gh workflow run "<workflow-name-or-id>" --ref "<branch>"
```
- `gh workflow run` は対象 workflow と `--ref` を明示できる場合のみ実施する。

6. 補助情報の取得（必要時のみ）
```bash
gh run view <run-id> --job <job-id> --log
gh run download <run-id> --dir ./artifacts/<run-id>
```

## 禁止事項
- `Sigumaa/calt` 以外の repository に対する `gh workflow` / `gh run` 操作。
- `gh ... --repo <other-owner/other-repo>` の使用。
- 認証未完了のまま rerun / cancel / workflow dispatch を実行すること。
- `gh api` を使った直接的な workflow 実行状態改変。
- ワークフロー運用を超える実装変更（コード編集、CI設計変更、権限設定変更）。

## 品質チェック
- 実行前に `gh repo view` と `gh auth status` の結果を確認する。
- 実行後は `workflow名/run_id/実行コマンド/結果` を短く記録する。
- トリガーテストは `references/trigger-test-log.md` に追記する。
- `description` を変更した場合は差分影響を記録する。

## 返答方針
- 返答は日本語で、実行した `gh workflow` / `gh run` コマンドを順序どおりに示す。
- 失敗時は失敗コマンド、原因、次の最小手順（例: 認証、対象指定）を分けて示す。
- 対象外依頼は「`Sigumaa/calt` 限定のため非対応」と明示して停止する。
