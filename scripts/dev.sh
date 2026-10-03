#!/usr/bin/env bash
# Runs a command in the infra-agent dev container (python, uv, git, terraform, opa).
set -euo pipefail
cd "$(dirname "$0")/.."
MSYS_NO_PATHCONV=1 exec docker compose run --rm -T dev "$@"
