#!/usr/bin/env bash
# pulse.sh - thin wrapper around `docker compose` for the Pulse stack.
#
# Pins the project's compose file + .env so every command "just works"
# from the repo root. Linux / macOS counterpart of pulse.ps1.
#
# Usage:
#   ./pulse.sh up -d                          # start the stack
#   ./pulse.sh up -d --build ingest           # rebuild + start one service
#   ./pulse.sh down                           # stop (preserves volumes)
#   ./pulse.sh down -v                        # stop + wipe volumes
#   ./pulse.sh ps                             # list containers
#   ./pulse.sh logs -f ingest                 # tail one service's logs
#   ./pulse.sh exec ingest bash               # shell into a container
#   ./pulse.sh exec postgres psql -U pulse -d pulse
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
COMPOSE_FILE="$SCRIPT_DIR/infra/docker-compose.yml"
ENV_FILE="$SCRIPT_DIR/.env"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "Missing $ENV_FILE. Copy .env.example to .env first." >&2
    exit 1
fi

exec docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" "$@"
