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

## Compose導入/確認（OS別）
### Ubuntu/Debian
1. Compose V2プラグインを導入: `sudo apt-get update && sudo apt-get install -y docker-compose-plugin`
2. 確認: `docker --version` と `docker compose version`
3. 旧コマンドが必要な場合のみ: `sudo apt-get install -y docker-compose` と `docker-compose version`

### macOS
1. Docker Desktopを導入: `brew install --cask docker-desktop`
2. Docker Desktopを起動して初期化完了を待つ
3. 確認: `docker --version` と `docker compose version`
4. 旧コマンドが必要な場合のみ: `brew install docker-compose`

### Windows（WSL含む）
1. WindowsへDocker Desktopを導入し、WSL 2連携を有効化
2. PowerShellまたはWSL端末で確認: `docker --version` と `docker compose version`
3. WSL内で旧コマンドが必要な場合のみ: `sudo apt-get update && sudo apt-get install -y docker-compose`
4. 端末ごとの差分確認は `bash scripts/check_docker_compose.sh` を利用

## 備考
- 実行対象は `tests/unit` と `tests/integration`。
- `tests/integration/` にDocker専用テストは追加しない。
