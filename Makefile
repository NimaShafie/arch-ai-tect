# Makefile
# - Keeps: kit, serve
# - Serve runs detached; auto-detects compose/docker-compose.yml in ./ or ./compose
# - Adds: logs, ps, restart, rebuild, sh, stop, clean, serve-tmux

SHELL := /bin/bash

# ---- Compose autodetect (root or ./compose) ----------------------------------
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

.PHONY: kit serve logs ps stop restart rebuild sh clean serve-tmux help
.DEFAULT_GOAL := help

help:
	@echo "Targets:"
	@echo "  kit           Build/pull images (Compose) or no-op (Local)"
	@echo "  serve         Start services detached (Compose up -d; Local via nohup)"
	@echo "  logs          Tail logs (Compose) or tail local log"
	@echo "  ps            Show process status (Compose) or local PID"
	@echo "  sh S=<svc>    Exec shell in service (Compose only)"
	@echo "  restart       Restart services"
	@echo "  rebuild       Rebuild images then start (Compose)"
	@echo "  stop          Stop services"
	@echo "  clean         Stop + remove volumes/orphans (Compose) or clean local files"
	@echo "  serve-tmux    Run 'serve' inside tmux session 'kit'"

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

serve-tmux:
	@tmux has-session -t kit 2>/dev/null || tmux new -d -s kit 'make serve && exec bash'
	@echo "[serve-tmux] Attach: tmux attach -t kit"

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
	@echo "[sh] Not available without Compose."
	exit 2
endif

restart:
ifeq ($(USE_COMPOSE),1)
	$(COMPOSE) restart
else
	@if [ -f $(LOCAL_PID) ]; then \
		kill $$(cat $(LOCAL_PID)) || true; \
		rm -f $(LOCAL_PID); \
	fi
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
	@if [ -f $(LOCAL_PID) ]; then \
		echo "[stop] Killing PID $$(cat $(LOCAL_PID))"; \
		kill $$(cat $(LOCAL_PID)) || true; \
		rm -f $(LOCAL_PID); \
	else \
		echo "[stop] No PID file."; \
	fi
endif

clean:
ifeq ($(USE_COMPOSE),1)
	$(COMPOSE) down -v --remove-orphans
else
	@rm -f $(LOCAL_PID) $(LOCAL_LOG)
	@echo "[clean] Removed local log and PID."
endif
