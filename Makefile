.PHONY: bootstrap install-profiles test-profiles start stop status clean help new-run env-test env-prod env-status kanban-board preflight cost-report server server-dev server-stop benchmark benchmark-quick benchmark-critics

PROFILES := translator wittgenstein quine frege koehn cho vaswani

# ── RUNTIME NOTE ─────────────────────────────────────────────────
# The Kanban gateway MUST run from the global ~/.hermes (not a project-local
# .hermes). SQLite WAL + macOS APFS locks cause disk I/O errors when the
# gateway and its worker children share the same HERMES_HOME subdirectory.
#
# Profiles are installed into ~/.hermes but their identity (SOUL.md, skills,
# config.yaml) lives version-controlled in profiles/ — isolation is per-profile,
# not per-runtime instance.
#
# The project .hermes/ directory is kept for reference only (profile sources).
# Gateway and Kanban always use HERMES_HOME = ~/.hermes.

# Hermes binary (auto-detect or override with HERMES_BIN=...)
HERMES_BIN := $(or $(shell which hermes 2>/dev/null),$(HOME)/.local/bin/hermes)

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

bootstrap: install-profiles kanban-board ## Full bootstrap: install profiles + create kanban board
	@echo ""
	@echo "Bootstrap complete."
	@echo "  Profiles installed in: ~/.hermes/profiles/"
	@echo "  Kanban board:          translation (EN→DE Translation Pipeline)"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Choose environment:  make env-prod  OR  make env-test"
	@echo "  2. Verify profiles:     make test-profiles"
	@echo "  3. Start gateway:       make start"
	@echo "  4. Open dashboard:      hermes dashboard --port 9229"

install-profiles: ## Install all 7 agent profiles into ~/.hermes
	@for profile in $(PROFILES); do \
		echo "Installing profile: $$profile..."; \
		$(HERMES_BIN) profile install -y "$(CURDIR)/profiles/$$profile" --name $$profile --force 2>&1 || \
			echo "  -> FAILED: $$profile"; \
	done

kanban-board: ## Create the 'translation' kanban board in ~/.hermes (idempotent)
	@if $(HERMES_BIN) kanban boards list 2>&1 | grep -q "^│ translation"; then \
		echo "Board 'translation' already exists — skipping."; \
	else \
		$(HERMES_BIN) kanban boards create translation \
			--name "EN→DE Translation Pipeline" \
			--color "#8c4aec" \
			--default-workdir "$(CURDIR)/corpus/runs"; \
		echo "Board 'translation' created."; \
	fi

test-profiles: ## Verify all profiles are installed in ~/.hermes
	@echo "HERMES_HOME = $$HOME/.hermes"
	@echo "---"
	@for profile in $(PROFILES); do \
		if [ -d "$$HOME/.hermes/profiles/$$profile" ]; then \
			echo "OK:      $$profile"; \
		else \
			echo "MISSING: $$profile"; \
		fi; \
	done

start: ## Start the Kanban gateway
	$(HERMES_BIN) gateway start

stop: ## Stop the Kanban gateway
	$(HERMES_BIN) gateway stop

status: ## Show gateway and dispatcher status
	$(HERMES_BIN) gateway status

dashboard: ## Open Hermes dashboard on port 9229 (avoids conflict with default 9119)
	$(HERMES_BIN) dashboard --port 9229

new-run: ## Create a new translation run from template
	@RUN_DATE=$$(date +%Y-%m-%d); \
	RUN_SEQ=$$(ls -d $(CURDIR)/corpus/runs/$${RUN_DATE}_* 2>/dev/null | wc -l | tr -d ' '); \
	RUN_SEQ=$$(printf "%03d" $$(( RUN_SEQ + 1 ))); \
	RUN_ID="$${RUN_DATE}_$${RUN_SEQ}"; \
	RUN_DIR="$(CURDIR)/corpus/runs/$${RUN_ID}"; \
	cp -R "$(CURDIR)/corpus/runs/.template" "$${RUN_DIR}"; \
	sed -i '' "s/run_id: \"\"/run_id: \"$${RUN_ID}\"/" "$${RUN_DIR}/manifest.yml"; \
	sed -i '' "s/created_at: \"\"/created_at: \"$$(date -u +%Y-%m-%dT%H:%M:%SZ)\"/" "$${RUN_DIR}/manifest.yml"; \
	echo "Created run: $${RUN_ID}"; \
	echo "  Directory:  $${RUN_DIR}"; \
	echo ""; \
	echo "  Fill in before dispatching:"; \
	echo "    $${RUN_DIR}/source/raw.txt          ← paste raw source content here"; \
	echo "    $${RUN_DIR}/source/segments.json    ← segmented translation units"; \
	echo "    $${RUN_DIR}/manifest.yml            ← run metadata"; \
	echo ""; \
	echo "  Generated after critics complete:"; \
	echo "    $${RUN_DIR}/final/review.md         ← bilingual table for client reviewer"

# ── ENVIRONMENT SWITCHING ────────────────────────────────────────
# Switch all agent configs between z.ai (test) and Anthropic (production)
# After switching, run 'make install-profiles' to apply to the runtime.

env-test: ## Switch to TEST environment (z.ai GLM models — free)
	@echo "Switching to TEST environment (z.ai)..."
	@# Translator → glm-4.6
	@sed -i '' 's|default: claude-opus-4-20250514|default: glm-4.6|' "$(CURDIR)/profiles/translator/config.yaml"
	@sed -i '' 's|default: claude-sonnet-4-20250514|default: glm-4.6|' "$(CURDIR)/profiles/translator/config.yaml"
	@sed -i '' 's|provider: anthropic|provider: zai|' "$(CURDIR)/profiles/translator/config.yaml"
	@sed -i '' 's|kanban_decomposer: claude-sonnet-4-20250514|kanban_decomposer: glm-4.6|' "$(CURDIR)/profiles/translator/config.yaml"
	@# Philosophers → glm-4.6
	@for profile in wittgenstein quine frege; do \
		sed -i '' 's|default: claude-opus-4-20250514|default: glm-4.6|' "$(CURDIR)/profiles/$$profile/config.yaml"; \
		sed -i '' 's|provider: anthropic|provider: zai|' "$(CURDIR)/profiles/$$profile/config.yaml"; \
	done
	@# Scientists → glm-4.6
	@for profile in koehn cho vaswani; do \
		sed -i '' 's|default: claude-sonnet-4-20250514|default: glm-4.6|' "$(CURDIR)/profiles/$$profile/config.yaml"; \
		sed -i '' 's|provider: anthropic|provider: zai|' "$(CURDIR)/profiles/$$profile/config.yaml"; \
	done
	@# Update environment.yml
	@sed -i '' 's|^active: production|active: test|' "$(CURDIR)/shared/environment.yml"
	@echo ""
	@echo "  Environment:  TEST (z.ai)"
	@echo "  Translator:   glm-4.6"
	@echo "  Philosophers: glm-4.6"
	@echo "  Scientists:   glm-4.6"
	@echo "  API key:      GLM_API_KEY"
	@echo ""
	@echo "  WARNING: Do NOT use test environment for client deliverables."
	@echo "  Run 'make install-profiles' to apply changes to Hermes runtime."

env-prod: ## Switch to PRODUCTION environment (Anthropic Claude — paid)
	@echo "Switching to PRODUCTION environment (Anthropic)..."
	@# Translator → claude-opus-4
	@sed -i '' 's|default: glm-4.6|default: claude-opus-4-20250514|' "$(CURDIR)/profiles/translator/config.yaml"
	@sed -i '' 's|provider: zai|provider: anthropic|' "$(CURDIR)/profiles/translator/config.yaml"
	@sed -i '' 's|kanban_decomposer: glm-4.6|kanban_decomposer: claude-sonnet-4-20250514|' "$(CURDIR)/profiles/translator/config.yaml"
	@# Philosophers → claude-opus-4
	@for profile in wittgenstein quine frege; do \
		sed -i '' 's|default: glm-4.6|default: claude-opus-4-20250514|' "$(CURDIR)/profiles/$$profile/config.yaml"; \
		sed -i '' 's|provider: zai|provider: anthropic|' "$(CURDIR)/profiles/$$profile/config.yaml"; \
	done
	@# Scientists → claude-sonnet-4
	@for profile in koehn cho vaswani; do \
		sed -i '' 's|default: glm-4.6|default: claude-sonnet-4-20250514|' "$(CURDIR)/profiles/$$profile/config.yaml"; \
		sed -i '' 's|provider: zai|provider: anthropic|' "$(CURDIR)/profiles/$$profile/config.yaml"; \
	done
	@# Update environment.yml
	@sed -i '' 's|^active: test|active: production|' "$(CURDIR)/shared/environment.yml"
	@echo ""
	@echo "  Environment:  PRODUCTION (Anthropic)"
	@echo "  Translator:   claude-opus-4-20250514"
	@echo "  Philosophers: claude-opus-4-20250514"
	@echo "  Scientists:   claude-sonnet-4-20250514"
	@echo "  API key:      ANTHROPIC_API_KEY"
	@echo ""
	@echo "  Run 'make install-profiles' to apply changes to Hermes runtime."

env-status: ## Show current environment
	@ENV=$$(grep '^active:' "$(CURDIR)/shared/environment.yml" | awk '{print $$2}'); \
	TMODEL=$$(grep 'default:' "$(CURDIR)/profiles/translator/config.yaml" | head -1 | awk '{print $$2}'); \
	PROV=$$(grep 'provider:' "$(CURDIR)/profiles/translator/config.yaml" | awk '{print $$2}'); \
	echo ""; \
	echo "  Environment: $$ENV"; \
	echo "  Provider:    $$PROV"; \
	echo "  Translator:  $$TMODEL"; \
	echo ""

preflight: ## Validate API credits and Kanban health before dispatching
	@bash "$(CURDIR)/scripts/preflight.sh"

ingest-feedback: ## Ingest client feedback: make ingest-feedback RUN=2026-06-02_001 FILE=~/feedback.json
	@if [ -z "$(RUN)" ] || [ -z "$(FILE)" ]; then \
		echo "Usage: make ingest-feedback RUN=<run_id> FILE=<input_file>"; \
		echo "  Example: make ingest-feedback RUN=2026-06-02_001 FILE=~/Downloads/tally-export.json"; \
		exit 1; \
	fi
	@bash "$(CURDIR)/scripts/ingest-feedback.sh" "$(RUN)" "$(FILE)"

reconcile: ## Reconcile feedback → approved.json: make reconcile RUN=2026-06-02_001
	@if [ -z "$(RUN)" ]; then \
		echo "Usage: make reconcile RUN=<run_id>"; \
		exit 1; \
	fi
	@python3 "$(CURDIR)/scripts/reconcile.py" "$(RUN)"

cost-report: ## Token & cost breakdown for a run: make cost-report RUN=2026-06-02_001
	@if [ -z "$(RUN)" ]; then echo "Usage: make cost-report RUN=<run_id>"; exit 1; fi
	node "$(CURDIR)/scripts/cost-report.mjs" "$(RUN)"

server: ## Start the API server on port 3000 (PORT=3000 to override)
	node "$(CURDIR)/scripts/server.mjs"

server-dev: ## Start API server with --watch auto-reload (Node 22+)
	node --watch "$(CURDIR)/scripts/server.mjs"

server-stop: ## Kill the API server
	@pkill -f "scripts/server.mjs" 2>/dev/null && echo "Server stopped." || echo "Server was not running."

benchmark: ## Translate + evaluate a candidate model: make benchmark RUN=2026-06-02_002 MODEL=claude-sonnet-4-20250514
	@if [ -z "$(RUN)" ] || [ -z "$(MODEL)" ]; then \
		echo "Usage: make benchmark RUN=<run_id> MODEL=<model_id>"; \
		echo "  Example: make benchmark RUN=2026-06-02_002 MODEL=claude-sonnet-4-20250514"; \
		exit 1; \
	fi
	python3 "$(CURDIR)/scripts/benchmark.py" --run "$(RUN)" --model "$(MODEL)"
	python3 "$(CURDIR)/scripts/eval-delta.py" --run "$(RUN)" --model "$(MODEL)"

benchmark-quick: ## Re-evaluate without re-translating (candidate already exists): make benchmark-quick RUN=... MODEL=...
	@if [ -z "$(RUN)" ] || [ -z "$(MODEL)" ]; then \
		echo "Usage: make benchmark-quick RUN=<run_id> MODEL=<model_id> [EXTRA=--include-critics]"; \
		exit 1; \
	fi
	python3 "$(CURDIR)/scripts/eval-delta.py" --run "$(RUN)" --model "$(MODEL)" $(EXTRA)

benchmark-critics: ## Run philosopher critics on candidate + update Delta Score: make benchmark-critics RUN=... MODEL=...
	@if [ -z "$(RUN)" ] || [ -z "$(MODEL)" ]; then \
		echo "Usage: make benchmark-critics RUN=<run_id> MODEL=<model_id> [CRITIC_MODEL=claude-opus-4-20250514]"; \
		exit 1; \
	fi
	python3 "$(CURDIR)/scripts/benchmark-critics.py" --run "$(RUN)" --model "$(MODEL)" $(if $(CRITIC_MODEL),--critic-model "$(CRITIC_MODEL)",)
	python3 "$(CURDIR)/scripts/eval-delta.py" --run "$(RUN)" --model "$(MODEL)" --include-critics

# ── V2 PIPELINE (Claude Code orchestrated) ──────────────────
# Replaces Hermes Kanban with direct Anthropic SDK calls.

translate: ## V2: Full translation pipeline — make translate SOURCE=path/to/source.txt
	@if [ -z "$(SOURCE)" ]; then echo "Usage: make translate SOURCE=<file> [CLIENT=<client-id>]"; exit 1; fi
	python3 "$(CURDIR)/v2/pipeline.py" --source "$(SOURCE)" --client "$(or $(CLIENT),example-client)"

translate-run: ## V2: Pipeline on existing run — make translate-run RUN=2026-06-18_001
	@if [ -z "$(RUN)" ]; then echo "Usage: make translate-run RUN=<run_id>"; exit 1; fi
	python3 "$(CURDIR)/v2/pipeline.py" --run "$(RUN)"

translate-dry: ## V2: Dry run (show prompts, no API calls) — make translate-dry RUN=...
	@if [ -z "$(RUN)" ]; then echo "Usage: make translate-dry RUN=<run_id>"; exit 1; fi
	python3 "$(CURDIR)/v2/pipeline.py" --run "$(RUN)" --dry-run

audit: ## V2: Run scientist audits — make audit RUN=2026-06-18_001
	@if [ -z "$(RUN)" ]; then echo "Usage: make audit RUN=<run_id>"; exit 1; fi
	python3 "$(CURDIR)/v2/pipeline.py" --run "$(RUN)" --audit

v2-test: ## V2: Run test suite
	python3 -m pytest "$(CURDIR)/v2/tests/" -v

v2-preflight: ## V2: Verify API key and environment
	python3 "$(CURDIR)/v2/pipeline.py" --preflight

v2-install: ## V2: Install Python dependencies
	pip install -r "$(CURDIR)/v2/requirements.txt"

clean: ## Remove project .hermes/ cache (safe — does NOT touch ~/.hermes)
	@echo "This will DELETE the project-local .hermes/ cache at $(CURDIR)/.hermes"
	@echo "Your personal ~/.hermes (gateway, profiles, kanban) will NOT be affected."
	@echo "Press Ctrl+C to cancel, or Enter to continue..."
	@read _confirm
	rm -rf "$(CURDIR)/.hermes"
	@echo "Cleaned."
