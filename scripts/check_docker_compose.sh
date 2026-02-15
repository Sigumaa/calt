#!/usr/bin/env bash

set -u
set -o pipefail

has_docker=0
has_compose_v2=0
has_compose_v1=0

print_section() {
  printf '\n== %s ==\n' "$1"
}

run_check() {
  local label="$1"
  shift

  local output
  local status

  printf '\n[%s]\n' "$label"
  printf 'コマンド: %s\n' "$*"

  output="$("$@" 2>&1)"
  status=$?

  if [ $status -eq 0 ]; then
    printf '結果: OK\n'
  else
    printf '結果: NG (exit %s)\n' "$status"
  fi

  if [ -n "$output" ]; then
    printf '%s\n' "$output" | sed 's/^/  /'
  fi

  return $status
}

print_section "Docker CLI"

if command -v docker >/dev/null 2>&1; then
  has_docker=1
  run_check "docker --version" docker --version || true

  if run_check "docker info" docker info; then
    :
  else
    printf '補足: Dockerデーモン未起動、または権限不足の可能性があります。\n'
  fi
else
  printf '\n[docker --version]\n'
  printf 'コマンド: docker --version\n'
  printf '結果: 未検出 (docker コマンドが見つかりません)\n'

  printf '\n[docker info]\n'
  printf 'コマンド: docker info\n'
  printf '結果: 未実行 (docker コマンド未検出)\n'
fi

print_section "Docker Compose"

if [ $has_docker -eq 1 ]; then
  if run_check "docker compose version" docker compose version; then
    has_compose_v2=1
  fi
else
  printf '\n[docker compose version]\n'
  printf 'コマンド: docker compose version\n'
  printf '結果: 未実行 (docker コマンド未検出)\n'
fi

if command -v docker-compose >/dev/null 2>&1; then
  has_compose_v1=1
  run_check "docker-compose version" docker-compose version || true
else
  printf '\n[docker-compose version]\n'
  printf 'コマンド: docker-compose version\n'
  printf '結果: 未検出 (docker-compose コマンドが見つかりません)\n'
fi

print_section "案内"

if [ $has_compose_v2 -eq 1 ] && [ $has_compose_v1 -eq 1 ]; then
  printf 'docker compose と docker-compose の両方が利用可能です。\n'
  printf '新規手順は Compose V2 (docker compose) を推奨します。\n'
elif [ $has_compose_v2 -eq 1 ] && [ $has_compose_v1 -eq 0 ]; then
  printf 'Compose V2 (docker compose) のみ利用可能です。\n'
  printf 'docker-compose 前提の手順は docker compose に置き換えてください。\n'
elif [ $has_compose_v2 -eq 0 ] && [ $has_compose_v1 -eq 1 ]; then
  printf 'docker-compose のみ利用可能です。\n'
  printf 'Docker Desktop または docker-compose-plugin を導入し、docker compose への移行を推奨します。\n'
else
  printf 'Compose コマンドが見つかりませんでした。\n'
  printf '.codex/DOCKER_TESTING.md のOS別手順に従って導入してください。\n'
fi
