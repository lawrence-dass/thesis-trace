# ThesisTrace task runner.
#
# Every target is one token to a permission checker (`Bash(make *)` covers them
# all), which is the point: 47% of this project's shell calls were chains like
# `set -a && source ../.env && set +a && uv run pytest`, and a permission rule is
# a PREFIX match — it can never match a chain whose first segment is `set -a`.
# The .env sourcing that forced those chains now lives here, paid once.
#
# `make` with no target lists what is available.

ROOT := $(shell pwd)
LOADENV := set -a && . $(ROOT)/.env && set +a
DC := thesistrace-pg

.DEFAULT_GOAL := help
.PHONY: help test test-one lint api web web-lint web-test web-build web-types \
        migrate migration db-up db-down psql pipeline py fmt

help:  ## List targets
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

# --- backend ---------------------------------------------------------------

# The authoritative guard lives in backend/tests/conftest.py, which compares what the
# two URLs POINT AT (host, port, database) rather than their text and refuses beside the
# drop_all itself — a direct `pytest` never reaches a make target. This is the cheap
# early check; both are needed.
test:  ## Backend tests (refuses to run against the dev database)
	@$(call safe,$(ARGS))
	@cd backend && $(LOADENV) && \
	if [ -z "$$TEST_DATABASE_URL" ]; then \
	  echo "refusing: TEST_DATABASE_URL is not set — the teardown drops every table."; \
	  exit 1; \
	fi; \
	uv run pytest -q $(ARGS)

test-one:  ## One test file or node: make test-one T=tests/test_foo.py::test_bar
	@if [ -z "$(T)" ]; then echo "usage: make test-one T=tests/test_x.py::test_y"; exit 1; fi
	@$(MAKE) test ARGS="$(T)"

lint:  ## ruff check (matches CI)
	@cd backend && uv run ruff check .

fmt:  ## ruff format
	@cd backend && uv run ruff format .

api:  ## Backend on :8001 — NOT :8000, which is the riskpulse dev server
	@cd backend && $(LOADENV) && uv run uvicorn app.main:app --port 8001 --reload

pipeline:  ## Full batch pipeline (LIVE EDGAR fetches — name every CIK first)
	@cd backend && $(LOADENV) && uv run python -m pipeline.run

py:  ## Run a script with the backend env: make py F=scripts/recanonicalize.py
	@$(call safe,$(F) $(ARGS))
	@if [ ! -f "$(ROOT)/$(F)" ]; then echo "no such script: $(F)"; exit 1; fi
	@cd backend && $(LOADENV) && uv run python "$(ROOT)/$(F)" $(ARGS)

# --- database --------------------------------------------------------------

db-up:  ## Start the Postgres container
	@docker start $(DC) || docker run -d --name $(DC) -p 5432:5432 \
	  -e POSTGRES_PASSWORD=devpass -v thesistrace-pgdata:/var/lib/postgresql/data postgres:17

db-down:  ## Stop the Postgres container (data survives)
	@docker stop $(DC)

psql:  ## Query the dev database: make psql Q="select 1"
	@docker exec $(DC) psql -U postgres -d thesistrace -c "$(Q)"

# Variables interpolate into a shell line, so `make py F='x; rm -rf .'` would otherwise
# run whatever follows the semicolon — and `Bash(make *)` pre-approves the lot, so it
# would run WITHOUT a prompt. Metacharacters are rejected rather than escaped: every
# legitimate value here is a path, a pytest node id or a flag.
define safe
	case '$(1)' in \
	  *[\;\&\|\`\$$\(\)\<\>\!]*) \
	    echo "refusing: '$(1)' contains shell metacharacters"; exit 1;; \
	esac
endef

migrate:  ## alembic upgrade head (run from the repo root, as CI does)
	@$(LOADENV) && uv run --project backend alembic upgrade head

migration:  ## New revision: make migration M="add widgets table"
	@if [ -z "$(M)" ]; then echo 'usage: make migration M="what it does"'; exit 1; fi
	@$(LOADENV) && uv run --project backend alembic revision -m "$(M)"

# --- frontend --------------------------------------------------------------

web:  ## Frontend on :3001, pointed at the :8001 backend
	@cd frontend && NEXT_PUBLIC_API_BASE_URL=http://localhost:8001 npm run dev -- --port 3001

web-lint:  ## eslint
	@cd frontend && npm run lint

web-test:  ## vitest run
	@cd frontend && npm test

web-types:  ## tsc --noEmit
	@cd frontend && npx tsc --noEmit

web-build:  ## next build (matches CI)
	@cd frontend && npm run build
