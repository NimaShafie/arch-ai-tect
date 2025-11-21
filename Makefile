# Makefile — Architecture Workbench
# - Keeps full docker compose helpers (kit/serve/logs/ps/...).
# - Adds Python venv/bootstrap, FastAPI server (API), MkDocs build/serve,
#   and project helpers (create, brief, choices, generate).

SHELL := /bin/bash

# ---- Python tooling ----------------------------------------------------------
PY      ?= python3
VENV    ?= .venv
PIP     := $(VENV)/bin/pip
UVICORN := $(VENV)/bin/uvicorn
MKDOCS  := $(VENV)/bin/mkdocs

# ---- Compose autodetect (root or ./compose) ---------------------------------
COMPOSE_CANDIDATES := compose.yml docker-compose.yml compose/compose.yml compose/docker-compose.yml
FOUND_COMPOSE := $(firstword $(foreach f,$(COMPOSE_CANDIDATES),$(wildcard $(f))))
ifeq ("$(FOUND_COMPOSE)","")
  USE_COMPOSE := 0
else
  USE_COMPOSE := 1
  COMPOSE := docker compose -f $(FOUND_COMPOSE)
endif

# ---- Local fallback (when no Compose file) -----------------------------------
SERVE_CMD ?= npm run dev
LOCAL_LOG ?= .server.log
LOCAL_PID ?= .server.pid

# ---- API config --------------------------------------------------------------
API_HOST ?= 127.0.0.1
API_PORT ?= 5058
API_APP  ?= server.app:app

# ---- Defaults ----------------------------------------------------------------
.PHONY: help venv bootstrap kit serve logs ps sh restart rebuild stop clean \
        api api-stop api-restart \
        nav docs docs-serve \
        proj-new proj-brief proj-choices proj-generate
.DEFAULT_GOAL := help

help:
	@echo "Targets:"
	@echo "  venv           Create .venv if missing"
	@echo "  bootstrap      Install Python deps (API + MkDocs)"
	@echo "  api            Run FastAPI (uvicorn) on $(API_HOST):$(API_PORT)"
	@echo "  api-stop       Kill uvicorn on $(API_PORT)"
	@echo "  api-restart    Restart the API"
	@echo "  nav            Regenerate Projects nav"
	@echo "  docs           Build MkDocs (clean)"
	@echo "  docs-serve     Serve MkDocs locally (127.0.0.1:8000)"
	@echo "  proj-new       Create a project: make proj-new N='Name' S='slug' T='Nav Title'"
	@echo "  proj-brief     Post brief JSON file: make proj-brief S='slug' F='path/to/brief.json'"
	@echo "  proj-choices   Set diagram/dialect choices: make proj-choices S='slug' TYPES='a,b' DIALECTS='x,y'"
	@echo "  proj-generate  Generate artifacts for project: make proj-generate S='slug' REFINE=1"
	@echo "  kit/serve/...  Docker compose helpers (unchanged)"

# --- Python env & deps --------------------------------------------------------
venv:
	@if [ ! -d $(VENV) ]; then $(PY) -m venv $(VENV); fi

bootstrap: venv
	$(PIP) install -r server/requirements.txt
	$(PIP) install mkdocs mkdocs-material mkdocs-macros-plugin mkdocs-exclude pymdown-extensions

# --- API server ---------------------------------------------------------------
api: venv
	$(UVICORN) $(API_APP) --host $(API_HOST) --port $(API_PORT) --reload

api-stop:
	@pkill -f "uvicorn .*$(API_APP).*$(API_PORT)" || true

api-restart: api-stop api

# --- MkDocs (generated Projects nav, build/serve) -----------------------------
nav: venv
	$(PY) -c "from server.services.mkdocs_nav import build_nav; build_nav()"
	$(PY) server/services/mkdocs_projects_index.py

docs: nav
	$(MKDOCS) build --clean

docs-serve: nav
	$(MKDOCS) serve

# --- Project helpers (Option A flow via API) ----------------------------------
# Usage:
#   make proj-new N="Disney+ Clone" S="disney-plus" T="Disney+ Clone"
proj-new:
	@test -n "$(N)" || (echo "Set N='Name'"; exit 2)
	@SLUG="$(S)"; \
	if [ -z "$$SLUG" ]; then \
	  SLUG="$$(printf '%s' "$(N)" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr -cd 'a-z0-9-')"; \
	fi; \
	TITLE="$(T)"; \
	if [ -z "$$TITLE" ]; then TITLE="$(N)"; fi; \
	curl -sS -X POST "http://$(API_HOST):$(API_PORT)/projects" \
	  -H "Content-Type: application/json" \
	  -d "$$(jq -n --arg name "$(N)" --arg slug "$$SLUG" --arg nav "$$TITLE" \
	        '{name:$$name, slug:$$slug, nav_title:$$nav}')" | jq .

#   make proj-brief S="disney-plus" F="docs/projects/disney-plus/brief.json"
proj-brief:
	@test -n "$(S)" || (echo "Set S='slug'"; exit 2)
	@test -n "$(F)" || (echo "Set F='path/to/brief.json'"; exit 2)
	curl -sS -X POST "http://$(API_HOST):$(API_PORT)/projects/$(S)/brief" \
	  -H "Content-Type: application/json" \
	  --data-binary "@$(F)" | jq .

#   make proj-choices S="disney-plus" TYPES="c4-context,c4-container,deployment,sequence,logical" DIALECTS="structurizr,plantuml,mermaid"
proj-choices:
	@test -n "$(S)" || (echo "Set S='slug'"; exit 2)
	@TYPES=$${TYPES:-"c4-context,c4-container,deployment,sequence,logical"}; \
	DIALS=$${DIALECTS:-"structurizr,plantuml,mermaid"}; \
	curl -sS -X POST "http://$(API_HOST):$(API_PORT)/projects/$(S)/choices" \
	  -H "Content-Type: application/json" \
	  -d "$$(
	    jq -n --arg types "$$TYPES" --arg di "$$DIALS" \
	     '{types:($$types|split(",")), dialects:($$di|split(","))}'
	  )" | jq .

#   make proj-generate S="disney-plus" REFINE=1
proj-generate:
	@test -n "$(S)" || (echo "Set S='slug'"; exit 2)
	@REF=$${REFINE:-1}; \
	curl -sS -X POST "http://$(API_HOST):$(API_PORT)/projects/$(S)/generate" \
	  -H "Content-Type: application/json" \
	  -d "$$(jq -n --argjson r $$REF '{refine: ($$r==1)}')" | jq .

#   run in detached (run everthing in one terminal)
api-detach:
	@nohup $(UVICORN) $(API_APP) --host $(API_HOST) --port $(API_PORT) --reload \
	    > .api.log 2>&1 & echo $$! > .api.pid; \
	echo "[api-detach] PID $$(cat .api.pid). Logs: .api.log"

api-detach-stop:
	@[ -f .api.pid ] && { echo "Stopping PID $$(cat .api.pid)"; kill $$(cat .api.pid) || true; rm -f .api.pid; } || echo "No .api.pid"


# --- Compose helpers (unchanged) ----------------------------------------------
kit:
ifeq ($(USE_COMPOSE),1)
	$(COMPOSE) pull
	$(COMPOSE) build
else
	@echo "[kit] No compose file found (looked for: $(COMPOSE_CANDIDATES)). Nothing to build."
endif

serve:
ifeq ($(USE_COMPOSE),1)
	$(COMPOSE) up -d --remove-orphans --wait
	@echo "[serve] Started with $(FOUND_COMPOSE)."
else
	@echo "[serve] Starting local: $(SERVE_CMD)"
	@nohup bash -lc '$(SERVE_CMD)' > $(LOCAL_LOG) 2>&1 & echo $$! > $(LOCAL_PID)
	@echo "[serve] PID $$(cat $(LOCAL_PID)). Logs: $(LOCAL_LOG)"
endif

logs:
ifeq ($(USE_COMPOSE),1)
	$(COMPOSE) logs -f --tail=200
else
	@test -f $(LOCAL_LOG) || { echo "[logs] No $(LOCAL_LOG)."; exit 1; }
	tail -f $(LOCAL_LOG)
endif

ps:
ifeq ($(USE_COMPOSE),1)
	$(COMPOSE) ps
else
	@if [ -f $(LOCAL_PID) ]; then \
	  echo "[ps] Local PID: $$(cat $(LOCAL_PID))"; \
	  ps -p $$(cat $(LOCAL_PID)) -o pid,ppid,etime,cmd; \
	else \
	  echo "[ps] No PID file found."; \
	fi
endif

sh:
ifeq ($(USE_COMPOSE),1)
	@test -n "$(S)" || (echo "Usage: make sh S=<service>"; exit 2)
	$(COMPOSE) exec $(S) sh || $(COMPOSE) exec $(S) /bin/bash
else
	@echo "[sh] Not available without Compose."; exit 2
endif

restart:
ifeq ($(USE_COMPOSE),1)
	$(COMPOSE) restart
else
	@if [ -f $(LOCAL_PID) ]; then kill $$(cat $(LOCAL_PID)) || true; rm -f $(LOCAL_PID); fi
	$(MAKE) serve
endif

rebuild:
ifeq ($(USE_COMPOSE),1)
	$(COMPOSE) up -d --build --remove-orphans
else
	@echo "[rebuild] Not applicable without Compose."
endif

stop:
ifeq ($(USE_COMPOSE),1)
	$(COMPOSE) down
else
	@if [ -f $(LOCAL_PID) ]; then echo "[stop] Killing PID $$(cat $(LOCAL_PID))"; kill $$(cat $(LOCAL_PID)) || true; rm -f $(LOCAL_PID); else echo "[stop] No PID file."; fi
endif

clean:
ifeq ($(USE_COMPOSE),1)
	$(COMPOSE) down -v --remove-orphans
else
	@rm -f $(LOCAL_PID) $(LOCAL_LOG)
	@echo "[clean] Removed local log and PID."
endif
