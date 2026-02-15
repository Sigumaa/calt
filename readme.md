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

3. セッション作成

```bash
SESSION_ID=$(uv run calt session create --goal "quickstart" | python -c 'import json,sys; print(json.load(sys.stdin)["id"])')
```

4. plan import

```bash
uv run calt plan import "$SESSION_ID" examples/sample_plan.json
```

5. 承認

```bash
uv run calt plan approve "$SESSION_ID" 1 --approved-by cli --source cli
uv run calt step approve "$SESSION_ID" step_list_workspace --approved-by cli --source cli
```

6. step 実行

```bash
uv run calt step execute "$SESSION_ID" step_list_workspace
```

7. ログ確認

```bash
uv run calt logs search "$SESSION_ID" --query "step_executed"
```
