#!/usr/bin/env bash
# Scripted demo. Runs INSIDE the dev container:  scripts/dev.sh bash scripts/demo.sh
# Attempt 1 opens SSH to the world (refused by policy), attempt 2 is private (a human approves it).
set -euo pipefail
cd "$(dirname "$0")/.."
export INFRA_AGENT_HOME="/data/demo-$(date +%s)"
NAME="demo${RANDOM}"

run() { echo "\$ $*"; "$@"; }

set +e
echo "\$ infra-agent propose --repo examples/tf-basic --proposer scripted --script examples/demo/ssh-then-private.yaml --name-prefix $NAME \"let me SSH into the web servers\""
OUT=$(uv run infra-agent propose --repo examples/tf-basic --proposer scripted \
  --script examples/demo/ssh-then-private.yaml --name-prefix "$NAME" --json "let me SSH into the web servers")
CODE=$?
set -e
RUN_ID=$(echo "$OUT" | python3 -c 'import json,sys; print(json.load(sys.stdin)["run_id"])')
echo "(exit code $CODE: paused for approval)"
run uv run infra-agent review "$RUN_ID"
SHA=$(uv run infra-agent review "$RUN_ID" --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["review"]["plan_sha256"])')
run uv run infra-agent approve "$RUN_ID" --plan-sha "$SHA" --approver demo-human
run uv run infra-agent audit verify "$RUN_ID"
