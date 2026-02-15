# Docker Testing

## 目的
- テスト実行をDocker内で再現し、実行環境差分の影響を減らす。
- テスト専用構成とし、永続ボリュームは使わない。
- コンテナ実行時のネットワークを無効化し、外部ネットワーク接続を前提にしない。

## 追加ファイル
- `Dockerfile`
- `docker-compose.test.yml`
- `scripts/docker_test.sh`

## 手順
1. 構文確認: `docker compose -f docker-compose.test.yml config` または `docker-compose -f docker-compose.test.yml config`
2. テスト実行: `bash scripts/docker_test.sh`

## 備考
- 実行対象は `tests/unit` と `tests/integration`。
- `tests/integration/` にDocker専用テストは追加しない。
