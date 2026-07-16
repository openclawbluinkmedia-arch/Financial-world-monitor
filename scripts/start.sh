#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f .env ]]; then
  echo "No .env file found. Copying .env.example -> .env"
  cp .env.example .env
  echo "Edit .env with your API keys before running."
fi

MODE="${1:-dev}"
COMPOSE_ARGS=(-f docker-compose.yml)

if [[ "$MODE" == "prod" ]]; then
  COMPOSE_ARGS+=(-f infra/docker-compose.yml)
fi

if [[ "${BUILD:-}" == "1" || "$*" == *--build* ]]; then
  COMPOSE_ARGS+=(--build)
fi

if [[ "${DETACH:-}" == "1" || "$*" == *--detach* ]]; then
  COMPOSE_ARGS+=(-d)
fi

echo "Starting FIOS in $MODE mode…"
set -x
docker compose "${COMPOSE_ARGS[@]}" up
