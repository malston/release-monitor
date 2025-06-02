# GitHub Release Monitoring - Development Makefile
# Provides simple commands for common development tasks

# Default shell
SHELL := /bin/bash

# Python virtual environment
VENV := venv
TEST_VENV := test-env
PYTHON := $(VENV)/bin/python3
PIP := $(VENV)/bin/pip
TEST_PYTHON := $(TEST_VENV)/bin/python3

# Configuration files
CONFIG := config.yaml
LOCAL_CONFIG := config-local.yaml
TEST_CONFIG := test-config.yaml

# Colors for output
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

# Default target - show help
.DEFAULT_GOAL := help

##@ General

.PHONY: help
help: ## Display this help message
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Setup & Installation

.PHONY: setup
setup: ## Complete local development setup (creates venv, installs deps, creates config)
	@printf "$(GREEN)Setting up development environment...$(NC)\n"
	@./scripts/setup-local.sh
	@printf "$(GREEN)✓ Setup complete! Don't forget to edit .env with your GitHub token$(NC)\n"

.PHONY: install
install: venv ## Install Python dependencies
	@printf "$(GREEN)Installing Python dependencies...$(NC)\n"
	@$(PIP) install -r requirements.txt
	@printf "$(GREEN)✓ Dependencies installed$(NC)\n"

.PHONY: venv
venv: ## Create Python virtual environment
	@if [ ! -d "$(VENV)" ]; then \
		printf "$(GREEN)Creating Python virtual environment...$(NC)\n"; \
		python3 -m venv $(VENV); \
		printf "$(GREEN)✓ Virtual environment created$(NC)\n"; \
	else \
		printf "$(YELLOW)Virtual environment already exists$(NC)\n"; \
	fi

.PHONY: clean-venv
clean-venv: ## Remove Python virtual environment
	@printf "$(RED)Removing virtual environment...$(NC)\n"
	@rm -rf $(VENV)
	@rm -rf test-env
	@printf "$(GREEN)✓ Virtual environments removed$(NC)\n"

##@ Development

.PHONY: run
run: install ## Run the monitoring script with default config
	@if [ ! -f ".env" ]; then \
		printf "$(RED)Error: .env file not found. Run 'make setup' first$(NC)\n"; \
		exit 1; \
	fi
	@printf "$(GREEN)Running GitHub release monitoring...$(NC)\n"
	@source .env && ./scripts/monitor.sh --config $(CONFIG)

.PHONY: run-local
run-local: install ## Run the monitoring script with local config
	@if [ ! -f ".env" ]; then \
		printf "$(RED)Error: .env file not found. Run 'make setup' first$(NC)\n"; \
		exit 1; \
	fi
	@if [ ! -f "$(LOCAL_CONFIG)" ]; then \
		printf "$(RED)Error: $(LOCAL_CONFIG) not found. Run 'make setup' first$(NC)\n"; \
		exit 1; \
	fi
	@printf "$(GREEN)Running GitHub release monitoring with local config...$(NC)\n"
	@source .env && ./scripts/monitor.sh --config $(LOCAL_CONFIG)

.PHONY: test
test: ## Run all tests
	@printf "$(GREEN)Running tests...$(NC)\n"
	@if [ -d "$(TEST_VENV)" ]; then \
		$(TEST_PYTHON) test.py; \
	elif [ -d "$(VENV)" ]; then \
		$(PYTHON) test.py; \
	else \
		printf "$(RED)No virtual environment found. Run 'make setup' first$(NC)\n"; \
		exit 1; \
	fi

.PHONY: check
check: lint validate test ## Run all checks (lint, validate, test)
	@printf "$(GREEN)✓ All checks passed!$(NC)\n"

.PHONY: lint
lint: venv ## Check code style (Python)
	@printf "$(GREEN)Checking code style...$(NC)\n"
	@if command -v pylint &> /dev/null; then \
		$(PYTHON) -m pylint github_monitor.py || true; \
	else \
		printf "$(YELLOW)pylint not installed, skipping Python linting$(NC)\n"; \
	fi
	@if command -v shellcheck &> /dev/null; then \
		shellcheck scripts/*.sh ci/*.sh ci/tasks/*/*.sh || true; \
	else \
		printf "$(YELLOW)shellcheck not installed, skipping shell script linting$(NC)\n"; \
	fi
	@printf "$(GREEN)✓ Linting complete$(NC)\n"

.PHONY: format
format: venv ## Format Python code with black
	@printf "$(GREEN)Formatting Python code...$(NC)\n"
	@if $(PIP) show black &> /dev/null; then \
		$(PYTHON) -m black github_monitor.py test.py; \
		printf "$(GREEN)✓ Code formatted$(NC)\n"; \
	else \
		printf "$(YELLOW)black not installed. Install with: pip install black$(NC)\n"; \
	fi

##@ CI/CD Pipeline

.PHONY: validate
validate: ## Validate Concourse pipeline and configurations
	@printf "$(GREEN)Validating pipeline configuration...$(NC)\n"
	@./ci/validate.sh

.PHONY: pipeline-set-test
pipeline-set-test: ## Deploy pipeline to test environment
	@printf "$(GREEN)Deploying pipeline to test...$(NC)\n"
	./ci/fly.sh set -t test -f test

.PHONY: pipeline-set-prod
pipeline-set-prod: ## Deploy pipeline to production
	@printf "$(GREEN)Deploying pipeline to production...$(NC)\n"
	@printf "$(YELLOW)Warning: This will deploy to production!$(NC)\n"
	@read -p "Continue? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		./ci/fly.sh set -t prod -f prod; \
	else \
		printf "$(RED)Deployment cancelled$(NC)\n"; \
	fi

.PHONY: pipeline-destroy
pipeline-destroy: ## Destroy pipeline (prompts for target)
	@read -p "Target (test/prod): " target; \
	printf "$(RED)Destroying pipeline from $$target...$(NC)\n"; \
	./ci/fly.sh destroy -t $$target

##@ Utilities

.PHONY: show-config
show-config: ## Display current configuration
	@printf "$(GREEN)Current configuration:$(NC)\n"
	@if [ -f "$(CONFIG)" ]; then \
		printf "=== $(CONFIG) ===\n"; \
		cat $(CONFIG); \
	fi
	@if [ -f ".env" ]; then \
		printf "\n=== Environment Variables (.env) ===\n"; \
		grep -v '^#' .env | grep -v '^$$' | sed 's/=.*/=***/' || true; \
	else \
		printf "$(YELLOW)No .env file found$(NC)\n"; \
	fi

.PHONY: watch
watch: venv ## Run monitoring continuously (every 5 minutes)
	@printf "$(GREEN)Starting continuous monitoring (Ctrl+C to stop)...$(NC)\n"
	@while true; do \
		clear; \
		printf "$(GREEN)=== GitHub Release Monitoring - $$(date) ===$(NC)\n"; \
		source .env && ./scripts/monitor.sh --config $(CONFIG); \
		printf "\n$(YELLOW)Next check in 5 minutes...$(NC)\n"; \
		sleep 300; \
	done

.PHONY: debug
debug: venv ## Run monitoring with debug output
	@printf "$(GREEN)Running with debug output...$(NC)\n"
	@source .env && DEBUG=true ./scripts/monitor.sh --config $(CONFIG) --force-check

##@ Cleanup

.PHONY: clean
clean: ## Clean up generated files (keeps venv)
	@printf "$(YELLOW)Cleaning up generated files...$(NC)\n"
	@rm -f release_state.json
	@rm -f releases.json releases.yaml
	@rm -f *.log
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@printf "$(GREEN)✓ Cleanup complete$(NC)\n"

.PHONY: clean-all
clean-all: clean clean-venv ## Clean everything including virtual environments
	@printf "$(YELLOW)Cleaning all generated files and environments...$(NC)\n"
	@rm -f .env
	@rm -f config-local.yaml
	@printf "$(GREEN)✓ Full cleanup complete$(NC)\n"

##@ Docker (Future Enhancement)

.PHONY: docker-build
docker-build: ## Build Docker image (future enhancement)
	@printf "$(YELLOW)Docker support coming soon...$(NC)\n"
	@printf "This will build a containerized version of the monitoring tool\n"

.PHONY: docker-run
docker-run: ## Run in Docker container (future enhancement)
	@printf "$(YELLOW)Docker support coming soon...$(NC)\n"
	@printf "This will run the monitoring tool in a container\n"

##@ Git Helpers

.PHONY: git-status
git-status: ## Show git status including ignored files
	@printf "$(GREEN)Git status:$(NC)\n"
	@git status
	@printf "\n$(GREEN)Ignored files:$(NC)\n"
	@git status --ignored --short | grep '^!!' | sed 's/!! /  /' || printf "  None\n"

.PHONY: pre-commit
pre-commit: check ## Run checks before committing
	@printf "$(GREEN)Running pre-commit checks...$(NC)\n"
	@if [ -n "$$(git status --porcelain)" ]; then \
		printf "$(YELLOW)Warning: You have uncommitted changes$(NC)\n"; \
	fi
	@printf "$(GREEN)✓ Ready to commit!$(NC)\n"

.PHONY: create-release
create-release: ## Create a GitHub release (requires TAG, NAME, and optionally NOTES)
	@if [ -z "$(TAG)" ]; then \
		printf "$(RED)Error: TAG is required. Usage: make create-release TAG=v1.0.0 NAME='Release 1.0.0'$(NC)\n"; \
		exit 1; \
	fi
	@if [ -z "$(NAME)" ]; then \
		printf "$(RED)Error: NAME is required. Usage: make create-release TAG=v1.0.0 NAME='Release 1.0.0'$(NC)\n"; \
		exit 1; \
	fi
	@printf "$(GREEN)Creating GitHub release...$(NC)\n"
	@printf "  Tag: $(TAG)\n"
	@printf "  Name: $(NAME)\n"
	@printf "  Notes: $(or $(NOTES),New release)\n"
	@if command -v gh &> /dev/null; then \
		printf "$(YELLOW)Note: This requires a GitHub token with 'workflow' scope$(NC)\n"; \
		gh release create "$(TAG)" \
			--title "$(NAME)" \
			--notes "$(or $(NOTES),New release)" \
			--target main || \
		(printf "$(YELLOW)If the above failed due to permissions, you can:$(NC)\n" && \
		 printf "  1. Create the release manually on GitHub\n" && \
		 printf "  2. Update your token permissions at https://github.com/settings/tokens\n" && \
		 printf "  3. Use: gh auth refresh -s workflow\n"); \
	else \
		printf "$(RED)Error: GitHub CLI (gh) not installed. Install from: https://cli.github.com/$(NC)\n"; \
		exit 1; \
	fi

##@ Integration Testing

.PHONY: integration-test
integration-test: venv ## Run all integration tests
	@printf "$(GREEN)Running all integration tests...$(NC)\n"
	@source .env 2>/dev/null || true && ./tests/integration/test_monitor_self.sh
	@printf "$(GREEN)Running download integration tests...$(NC)\n"
	@source .env 2>/dev/null || true && ./tests/integration/test_monitor_download.sh

.PHONY: test-monitor-self
test-monitor-self: venv ## Test monitoring this repository's releases
	@printf "$(GREEN)Testing monitor on release-monitor repository...$(NC)\n"
	@source .env 2>/dev/null || true && $(PYTHON) tests/integration/test_monitor_self.py

.PHONY: test-download-integration
test-download-integration: venv ## Run download integration tests
	@printf "$(GREEN)Running download integration tests...$(NC)\n"
	@if [ ! -f ".env" ]; then \
		printf "$(YELLOW)Warning: .env file not found. Some tests may fail without GITHUB_TOKEN$(NC)\n"; \
	fi
	@source .env 2>/dev/null || true && ./tests/integration/test_monitor_download.sh

##@ Examples

.PHONY: example-json
example-json: venv ## Run monitoring and output JSON (example)
	@printf "$(GREEN)Example: JSON output$(NC)\n"
	@source .env && ./scripts/monitor.sh --config $(TEST_CONFIG) --format json | jq '.' || true

.PHONY: example-yaml
example-yaml: venv ## Run monitoring and output YAML (example)
	@printf "$(GREEN)Example: YAML output$(NC)\n"
	@source .env && ./scripts/monitor.sh --config $(TEST_CONFIG) --format yaml

.PHONY: example-new-releases
example-new-releases: venv ## Show only new releases (example)
	@printf "$(GREEN)Example: New releases only$(NC)\n"
	@source .env && ./scripts/monitor.sh --config $(TEST_CONFIG) --format json | \
		jq -r '.releases[] | "New release: \(.repository) \(.tag_name)"' || printf "No new releases found\n"

# Special targets
.PHONY: all
all: setup check ## Setup and run all checks

# Ensure virtual environment is activated for Python commands
$(PYTHON): venv

# Create directories if needed
$(shell mkdir -p logs tmp)