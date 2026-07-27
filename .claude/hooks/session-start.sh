#!/bin/bash
# SessionStart hook: brings up a working local dev environment for ThesisTrace
# on Claude Code on the web, with no manual steps.
#
# This sandbox has no Docker daemon and no outbound network access to
# data.sec.gov / api.tiingo.com (org network policy, not fixable here) — so
# this deliberately runs Postgres directly via apt/pg_ctlcluster instead of
# the docker-based flow HANDOFF.md describes for desktop sessions, and never
# attempts a live pipeline run. The committed test fixtures are enough to run
# the full backend test suite fully offline.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

REPO_ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$REPO_ROOT"

PG_VERSION=16
DB_USER=postgres
DB_PASSWORD=devpass
DB_NAME=thesistrace
TEST_DB_NAME=thesistrace_test

# --- 1. Postgres install (skip if already present) ---
if ! dpkg -s postgresql >/dev/null 2>&1; then
  echo "[session-start] installing postgresql..."
  apt-get update -qq
  apt-get install -y -qq postgresql
fi

# --- 2. Start the cluster (no systemd in this container, PID 1 isn't systemd) ---
if ! pg_lsclusters | awk '{print $4}' | grep -q "^online$"; then
  echo "[session-start] starting postgresql cluster..."
  pg_ctlcluster "$PG_VERSION" main start
  for i in $(seq 1 20); do
    su postgres -c "psql -c 'SELECT 1;'" >/dev/null 2>&1 && break
    sleep 0.5
  done
fi

# --- 3. Superuser password + databases (idempotent) ---
su postgres -c "psql -c \"ALTER USER $DB_USER PASSWORD '$DB_PASSWORD';\"" >/dev/null

for name in "$DB_NAME" "$TEST_DB_NAME"; do
  exists=$(su postgres -c "psql -tAc \"SELECT 1 FROM pg_database WHERE datname = '$name';\"")
  if [ "$exists" != "1" ]; then
    echo "[session-start] creating database $name..."
    su postgres -c "psql -c \"CREATE DATABASE $name;\""
  fi
done

# --- 4. .env (create only if missing — never clobber a real key a session/user added) ---
if [ ! -f "$REPO_ROOT/.env" ]; then
  echo "[session-start] creating .env from .env.example..."
  cp "$REPO_ROOT/.env.example" "$REPO_ROOT/.env"
  sed -i \
    -e "s#^DATABASE_URL=.*#DATABASE_URL=postgresql+asyncpg://$DB_USER:$DB_PASSWORD@127.0.0.1:5432/$DB_NAME#" \
    -e "s#^TEST_DATABASE_URL=.*#TEST_DATABASE_URL=postgresql+asyncpg://$DB_USER:$DB_PASSWORD@127.0.0.1:5432/$TEST_DB_NAME#" \
    "$REPO_ROOT/.env"
fi

# --- 5. Backend deps + schema (alembic.ini lives at repo root, run from there) ---
echo "[session-start] syncing backend deps and running migrations..."
(cd "$REPO_ROOT" && uv run --project backend --env-file .env alembic upgrade head)

# --- 6. Frontend deps ---
if [ -f "$REPO_ROOT/frontend/package.json" ]; then
  echo "[session-start] installing frontend deps..."
  (cd "$REPO_ROOT/frontend" && npm install --no-audit --no-fund --loglevel=error)
fi

echo "[session-start] done. Note: data.sec.gov and api.tiingo.com are blocked by this environment's network policy (org-level, not a hook bug) — live pipeline runs (pipeline/run.py) won't work here, but the full test suite (fixture-based, no live network) does."
