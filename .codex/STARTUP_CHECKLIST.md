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
