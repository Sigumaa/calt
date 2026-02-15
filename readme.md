# calt

## Quick Start

1. 依存同期

```bash
uv sync --dev
```

2. デーモン起動（別ターミナル）

```bash
export CALT_DAEMON_TOKEN=dev-token
export CALT_DAEMON_BASE_URL=http://127.0.0.1:8000
uv run calt-daemon --db-path data/calt.sqlite3 --data-root data
```

3. 最短操作を表示

```bash
uv run calt guide
```

4. 設定と主要API疎通を診断

```bash
uv run calt doctor
```

5. 最短フローを実行

```bash
uv run calt quickstart examples/sample_plan.json --goal "quickstart"
```

6. 対話ウィザードで実行

```bash
uv run calt wizard run
# 実行サマリに Plan Title / Goal を表示
```

7. 個別操作で実行する場合（JSON出力）

```bash
SESSION_ID=$(uv run calt session create --goal "quickstart" --json | python -c 'import json,sys; print(json.load(sys.stdin)["id"])')
uv run calt plan import "$SESSION_ID" examples/sample_plan.json --json
c
uv run calt step approve "$SESSION_ID" step_list_workspace --approved-by cli --source cli
uv run calt step execute "$SESSION_ID" step_list_workspace
uv run calt logs search "$SESSION_ID" --query "step_executed"
```

8. 次アクション提案を確認

```bash
uv run calt explain "$SESSION_ID"
uv run calt explain "$SESSION_ID" --json
# --json で plan_version / plan_title / pending_step_id / pending_step_status を確認可能
```

## サンプルPlan一覧と実行例

- `examples/sample_plan.json`: 最小のread-only 1step
- `examples/workspace_overview_plan.json`: `list_dir` + `read_file` でワークスペース概要を確認
- `examples/search_inspect_plan.json`: `run_shell_readonly` + `read_file` で検索と詳細確認
- `examples/preview_only_write_plan.json`: `write_file_preview` / `apply_patch mode=preview` の非破壊プレビュー
- `examples/c2_two_phase_apply_plan.json`: `write_file_preview` -> `write_file_apply` の二相適用（step出力参照を利用）
- `examples/c3_needs_replan_plan.json`: read-only失敗を意図的に起こし `needs_replan` 導線を確認

step入力の参照構文:

- `${steps.<step_id>.output}`
- `${steps.<step_id>.output.<field_path>}` (`.` 区切りでdictを辿る)

quickstart実行例:

```bash
uv run calt quickstart examples/workspace_overview_plan.json --goal "workspace overview"
uv run calt quickstart examples/search_inspect_plan.json --goal "search and inspect"
uv run calt quickstart examples/preview_only_write_plan.json --goal "preview only"
```

C-2実行例（applyを含むため `dev` profile 推奨）:

```bash
SESSION_ID=$(uv run calt session create --goal "c2 demo" --safety-profile dev --json | python -c 'import json,sys; print(json.load(sys.stdin)["id"])')
uv run calt plan import "$SESSION_ID" examples/c2_two_phase_apply_plan.json --json
uv run calt plan approve "$SESSION_ID" 1 --approved-by cli --source cli
uv run calt step approve "$SESSION_ID" step_preview_write --approved-by cli --source cli
uv run calt step approve "$SESSION_ID" step_apply_write --approved-by cli --source cli
uv run calt step execute "$SESSION_ID" step_preview_write
uv run calt step execute "$SESSION_ID" step_apply_write
```

C-3実行例（失敗後の `needs_replan` 導線確認）:

```bash
SESSION_ID=$(uv run calt session create --goal "c3 demo" --json | python -c 'import json,sys; print(json.load(sys.stdin)["id"])')
uv run calt plan import "$SESSION_ID" examples/c3_needs_replan_plan.json --json
uv run calt plan approve "$SESSION_ID" 1 --approved-by cli --source cli
uv run calt step approve "$SESSION_ID" step_fail_read_missing --approved-by cli --source cli
uv run calt step execute "$SESSION_ID" step_fail_read_missing
uv run calt explain "$SESSION_ID"
```

wizard実行例:

```bash
uv run calt wizard run
# plan file promptで examples/preview_only_write_plan.json などを入力
```

## Next Roadmap

- Safety Baseline（計画中）
- Guided CLI（計画中）
- 実用サンプルPlan（計画中）
