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

4. 最短フローを実行

```bash
uv run calt flow run --goal "quickstart" examples/sample_plan.json
```

5. 個別操作で実行する場合（JSON出力）

```bash
SESSION_ID=$(uv run calt session create --goal "quickstart" --json | python -c 'import json,sys; print(json.load(sys.stdin)["id"])')
uv run calt plan import "$SESSION_ID" examples/sample_plan.json --json
uv run calt plan approve "$SESSION_ID" 1 --approved-by cli --source cli
uv run calt step approve "$SESSION_ID" step_list_workspace --approved-by cli --source cli
uv run calt step execute "$SESSION_ID" step_list_workspace
uv run calt logs search "$SESSION_ID" --query "step_executed"
```
