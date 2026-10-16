#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [ $# -eq 0 ]; then
    MODE=local
    BASE_URL="http://localhost:8080"
else
    MODE=remote
    BASE_URL="${1%/}"
fi

if [ "$MODE" = "local" ]; then
    export SERVICE_FQDN_FRONTEND="$BASE_URL"
    echo "=== local mode: building + starting frontend, backend, db ==="
    docker compose down --remove-orphans >/dev/null 2>&1 || true
    docker compose up -d --build
else
    echo "=== remote mode: smoke-testing $BASE_URL ==="
fi

echo -n "waiting for /health "
for _ in $(seq 1 90); do
    if curl -sSf "$BASE_URL/health" >/dev/null 2>&1; then
        echo " ready"
        break
    fi
    echo -n "."
    sleep 1
done

echo
echo "=== GET / ==="
curl -fsS "$BASE_URL/" >/dev/null
echo "frontend ok"

echo "=== GET /health ==="
curl -fsS "$BASE_URL/health"
echo

PROJECT_NAME="smoke-test-project-$(date +%s)"
echo "=== POST /api/projects (frontend -> backend -> db write) ==="
curl -fsS -X POST "$BASE_URL/api/projects" \
    -H 'Content-Type: application/json' \
    -d "{\"name\":\"$PROJECT_NAME\",\"description\":\"Created by smoke-test.sh\",\"team_member_ids\":[]}" >/dev/null
echo "created $PROJECT_NAME"

echo "=== GET /api/projects (db read-back) ==="
curl -fsS "$BASE_URL/api/projects" | grep "$PROJECT_NAME" >/dev/null
echo "read-back ok"

echo
if [ "$MODE" = "local" ]; then
    echo "Local smoke test passed. The stack is still running at $BASE_URL."
    echo "Stop it with: docker compose down"
else
    echo "Remote smoke test passed: $BASE_URL"
fi
