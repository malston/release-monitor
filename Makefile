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

# Colors for output - set NO_COLOR=1 to disable colors
ifndef NO_COLOR
    GREEN := \033[0;32m
    YELLOW := \033[0;33m
    RED := \033[0;31m
    NC := \033[0m
else
    GREEN := 
    YELLOW := 
    RED := 
    NC := 
endif

# Default target - show help
.DEFAULT_GOAL := help

##@ General

.PHONY: help
help: ## Display this help message
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Setup & Installation

.PHONY: setup
setup: ## Complete local development setup (creates venv, installs deps, creates config)
	@echo "$(GREEN)Setting up development environment...$(NC)"
	@./scripts/setup-local.sh
	@echo "$(GREEN)✓ Setup complete! Don't forget to edit .env with your GitHub token$(NC)"

.PHONY: install
install: venv ## Install Python dependencies
	@echo "$(GREEN)Installing Python dependencies...$(NC)"
	@$(PIP) install -r requirements.txt
	@echo "$(GREEN)✓ Dependencies installed$(NC)"

.PHONY: venv
venv: ## Create Python virtual environment
	@if [ ! -d "$(VENV)" ]; then \
		echo "$(GREEN)Creating Python virtual environment...$(NC)"; \
		python3 -m venv $(VENV); \
		echo "$(GREEN)✓ Virtual environment created$(NC)"; \
	else \
		echo "$(YELLOW)Virtual environment already exists$(NC)"; \
	fi

.PHONY: clean-venv
clean-venv: ## Remove Python virtual environment
	@echo "$(RED)Removing virtual environment...$(NC)"
	@rm -rf $(VENV)
	@rm -rf test-env
	@echo "$(GREEN)✓ Virtual environments removed$(NC)"

##@ Development

.PHONY: run
run: install ## Run the monitoring script with default config
	@if [ ! -f ".env" ]; then \
		echo "$(RED)Error: .env file not found. Run 'make setup' first$(NC)"; \
		exit 1; \
	fi
	@echo "$(GREEN)Running GitHub release monitoring...$(NC)"
	@source .env && ./scripts/monitor.sh --config $(CONFIG)

.PHONY: run-local
run-local: install ## Run the monitoring script with local config
	@if [ ! -f ".env" ]; then \
		echo "$(RED)Error: .env file not found. Run 'make setup' first$(NC)"; \
		exit 1; \
	fi
	@if [ ! -f "$(LOCAL_CONFIG)" ]; then \
		echo "$(RED)Error: $(LOCAL_CONFIG) not found. Run 'make setup' first$(NC)"; \
		exit 1; \
	fi
	@echo "$(GREEN)Running GitHub release monitoring with local config...$(NC)"
	@source .env && ./scripts/monitor.sh --config $(LOCAL_CONFIG)

.PHONY: test
test: ## Run all tests
	@echo "$(GREEN)Running tests...$(NC)"
	@if [ -d "$(TEST_VENV)" ]; then \
		$(TEST_PYTHON) test.py; \
	elif [ -d "$(VENV)" ]; then \
		$(PYTHON) test.py; \
	else \
		echo "$(RED)No virtual environment found. Run 'make setup' first$(NC)"; \
		exit 1; \
	fi

.PHONY: check
check: lint validate test ## Run all checks (lint, validate, test)
	@echo "$(GREEN)✓ All checks passed!$(NC)"

.PHONY: lint
lint: venv ## Check code style (Python)
	@echo "$(GREEN)Checking code style...$(NC)"
	@if command -v pylint &> /dev/null; then \
		$(PYTHON) -m pylint github_monitor.py || true; \
	else \
		echo "$(YELLOW)pylint not installed, skipping Python linting$(NC)"; \
	fi
	@if command -v shellcheck &> /dev/null; then \
		shellcheck scripts/*.sh ci/*.sh ci/tasks/*/*.sh || true; \
	else \
		echo "$(YELLOW)shellcheck not installed, skipping shell script linting$(NC)"; \
	fi
	@echo "$(GREEN)✓ Linting complete$(NC)"

.PHONY: format
format: venv ## Format Python code with black
	@echo "$(GREEN)Formatting Python code...$(NC)"
	@if $(PIP) show black &> /dev/null; then \
		$(PYTHON) -m black github_monitor.py test.py; \
		echo "$(GREEN)✓ Code formatted$(NC)"; \
	else \
		echo "$(YELLOW)black not installed. Install with: pip install black$(NC)"; \
	fi

##@ CI/CD Pipeline

.PHONY: validate
validate: ## Validate Concourse pipeline and configurations
	@echo "$(GREEN)Validating pipeline configuration...$(NC)"
	@./ci/validate.sh

.PHONY: pipeline-set-test
pipeline-set-test: ## Deploy pipeline to test environment (public repos only)
	@echo "$(GREEN)Deploying pipeline to test (public repositories)...$(NC)"
	@echo "$(YELLOW)Note: For private repos, use 'make pipeline-set-test-with-key'$(NC)"
	@if [ -z "$$GITHUB_TOKEN" ]; then \
		echo "$(RED)Error: GITHUB_TOKEN environment variable not set$(NC)"; \
		echo "$(YELLOW)Please set: export GITHUB_TOKEN=\"your_github_token\"$(NC)"; \
		exit 1; \
	fi
	@fly -t test set-pipeline \
		-p github-release-monitor \
		-c ci/pipeline.yml \
		-l params/global.yml \
		-l params/test.yml \
		--var github_token="$$GITHUB_TOKEN" \
		--non-interactive

.PHONY: pipeline-set-test-with-key
pipeline-set-test-with-key: ## Deploy pipeline to test environment with SSH key for private repos
	@echo "$(GREEN)Deploying pipeline to test with SSH key...$(NC)"
	@SSH_KEY=""; \
	if [ -f ~/.ssh/id_ed25519 ]; then \
		SSH_KEY=~/.ssh/id_ed25519; \
		echo "$(GREEN)Using Ed25519 SSH key: ~/.ssh/id_ed25519$(NC)"; \
	elif [ -f ~/.ssh/id_rsa ]; then \
		SSH_KEY=~/.ssh/id_rsa; \
		echo "$(YELLOW)Using RSA SSH key: ~/.ssh/id_rsa$(NC)"; \
	else \
		echo "$(RED)Error: No SSH key found$(NC)"; \
		echo "$(YELLOW)Looked for: ~/.ssh/id_ed25519 (preferred) or ~/.ssh/id_rsa$(NC)"; \
		echo "$(YELLOW)Either create an SSH key or use 'make pipeline-set-test' for public repos$(NC)"; \
		exit 1; \
	fi; \
	if [ -z "$$GITHUB_TOKEN" ]; then \
		echo "$(RED)Error: GITHUB_TOKEN environment variable not set$(NC)"; \
		echo "$(YELLOW)Please set: export GITHUB_TOKEN=\"your_github_token\"$(NC)"; \
		exit 1; \
	fi; \
	fly -t test set-pipeline \
		-p github-release-monitor \
		-c ci/pipeline.yml \
		-l params/global.yml \
		-l params/test.yml \
		--var git_private_key="$$(cat $$SSH_KEY)" \
		--var github_token="$$GITHUB_TOKEN" \
		--non-interactive

.PHONY: pipeline-set-prod
pipeline-set-prod: ## Deploy pipeline to production
	@echo "$(GREEN)Deploying pipeline to production...$(NC)"
	@echo "$(YELLOW)Warning: This will deploy to production!$(NC)"
	@if [ -z "$$GITHUB_TOKEN" ]; then \
		echo "$(RED)Error: GITHUB_TOKEN environment variable not set$(NC)"; \
		echo "$(YELLOW)Please set: export GITHUB_TOKEN=\"your_github_token\"$(NC)"; \
		exit 1; \
	fi
	@read -p "Continue? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		fly -t prod set-pipeline \
			-p github-release-monitor \
			-c ci/pipeline.yml \
			-l params/global.yml \
			-l params/prod.yml \
			--var github_token="$$GITHUB_TOKEN" \
			--non-interactive; \
	else \
		echo "$(RED)Deployment cancelled$(NC)"; \
	fi

.PHONY: pipeline-set-prod-with-key
pipeline-set-prod-with-key: ## Deploy pipeline to production with SSH key for private repos
	@echo "$(GREEN)Deploying pipeline to production with SSH key...$(NC)"
	@echo "$(RED)Warning: This will deploy to production with SSH key access!$(NC)"
	@read -p "Continue? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		SSH_KEY=""; \
		if [ -f ~/.ssh/id_ed25519 ]; then \
			SSH_KEY=~/.ssh/id_ed25519; \
			echo "$(GREEN)Using Ed25519 SSH key: ~/.ssh/id_ed25519$(NC)"; \
		elif [ -f ~/.ssh/id_rsa ]; then \
			SSH_KEY=~/.ssh/id_rsa; \
			echo "$(YELLOW)Using RSA SSH key: ~/.ssh/id_rsa$(NC)"; \
		else \
			echo "$(RED)Error: No SSH key found$(NC)"; \
			echo "$(YELLOW)Looked for: ~/.ssh/id_ed25519 (preferred) or ~/.ssh/id_rsa$(NC)"; \
			exit 1; \
		fi; \
		if [ -z "$$GITHUB_TOKEN" ]; then \
			echo "$(RED)Error: GITHUB_TOKEN environment variable not set$(NC)"; \
			echo "$(YELLOW)Please set: export GITHUB_TOKEN=\"your_github_token\"$(NC)"; \
			exit 1; \
		fi; \
		fly -t prod set-pipeline \
			-p github-release-monitor \
			-c ci/pipeline.yml \
			-l params/global.yml \
			-l params/prod.yml \
			--var git_private_key="$$(cat $$SSH_KEY)" \
			--var github_token="$$GITHUB_TOKEN" \
			--non-interactive; \
	else \
		echo "$(RED)Deployment cancelled$(NC)"; \
	fi

.PHONY: pipeline-destroy
pipeline-destroy: ## Destroy pipeline (prompts for target)
	@read -p "Target (test/prod): " target; \
	echo "$(RED)Destroying pipeline from $$target...$(NC)"; \
	./ci/fly.sh destroy -t $$target

##@ Utilities

.PHONY: show-config
show-config: ## Display current configuration
	@echo "$(GREEN)Current configuration:$(NC)"
	@if [ -f "$(CONFIG)" ]; then \
		echo "=== $(CONFIG) ==="; \
		cat $(CONFIG); \
	fi
	@if [ -f ".env" ]; then \
		echo -e "\n=== Environment Variables (.env) ==="; \
		grep -v '^#' .env | grep -v '^$$' | sed 's/=.*/=***/' || true; \
	else \
		echo "$(YELLOW)No .env file found$(NC)"; \
	fi

.PHONY: watch
watch: venv ## Run monitoring continuously (every 5 minutes)
	@echo "$(GREEN)Starting continuous monitoring (Ctrl+C to stop)...$(NC)"
	@while true; do \
		clear; \
		echo "$(GREEN)=== GitHub Release Monitoring - $$(date) ===$(NC)"; \
		source .env && ./scripts/monitor.sh --config $(CONFIG); \
		echo -e "\n$(YELLOW)Next check in 5 minutes...$(NC)"; \
		sleep 300; \
	done

.PHONY: debug
debug: venv ## Run monitoring with debug output
	@echo "$(GREEN)Running with debug output...$(NC)"
	@source .env && DEBUG=true ./scripts/monitor.sh --config $(CONFIG) --force-check

##@ Cleanup

.PHONY: clean
clean: ## Clean up generated files (keeps venv)
	@echo "$(YELLOW)Cleaning up generated files...$(NC)"
	@rm -f release_state.json
	@rm -f releases.json releases.yaml
	@rm -f *.log
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "$(GREEN)✓ Cleanup complete$(NC)"

.PHONY: clean-all
clean-all: clean clean-venv ## Clean everything including virtual environments
	@echo "$(YELLOW)Cleaning all generated files and environments...$(NC)"
	@rm -f .env
	@rm -f config-local.yaml
	@echo "$(GREEN)✓ Full cleanup complete$(NC)"

##@ Docker (Future Enhancement)

.PHONY: docker-build
docker-build: ## Build Docker image (future enhancement)
	@echo "$(YELLOW)Docker support coming soon...$(NC)"
	@echo "This will build a containerized version of the monitoring tool"

.PHONY: docker-run
docker-run: ## Run in Docker container (future enhancement)
	@echo "$(YELLOW)Docker support coming soon...$(NC)"
	@echo "This will run the monitoring tool in a container"

##@ Git Helpers

.PHONY: git-status
git-status: ## Show git status including ignored files
	@echo "$(GREEN)Git status:$(NC)"
	@git status
	@echo -e "\n$(GREEN)Ignored files:$(NC)"
	@git status --ignored --short | grep '^!!' | sed 's/!! /  /' || echo "  None"

.PHONY: pre-commit
pre-commit: check ## Run checks before committing
	@echo "$(GREEN)Running pre-commit checks...$(NC)"
	@if [ -n "$$(git status --porcelain)" ]; then \
		echo "$(YELLOW)Warning: You have uncommitted changes$(NC)"; \
	fi
	@echo "$(GREEN)✓ Ready to commit!$(NC)"

.PHONY: create-release
create-release: ## Create a GitHub release (requires TAG, NAME, and optionally NOTES)
	@if [ -z "$(TAG)" ]; then \
		echo "$(RED)Error: TAG is required. Usage: make create-release TAG=v1.0.0 NAME='Release 1.0.0'$(NC)"; \
		exit 1; \
	fi
	@if [ -z "$(NAME)" ]; then \
		echo "$(RED)Error: NAME is required. Usage: make create-release TAG=v1.0.0 NAME='Release 1.0.0'$(NC)"; \
		exit 1; \
	fi
	@echo "$(GREEN)Creating GitHub release...$(NC)"
	@echo "  Tag: $(TAG)"
	@echo "  Name: $(NAME)"
	@echo "  Notes: $(or $(NOTES),New release)"
	@if command -v gh &> /dev/null; then \
		echo "$(YELLOW)Note: This requires a GitHub token with 'workflow' scope$(NC)"; \
		gh release create "$(TAG)" \
			--title "$(NAME)" \
			--notes "$(or $(NOTES),New release)" \
			--target main || \
		(echo "$(YELLOW)If the above failed due to permissions, you can:$(NC)" && \
		 echo "  1. Create the release manually on GitHub" && \
		 echo "  2. Update your token permissions at https://github.com/settings/tokens" && \
		 echo "  3. Use: gh auth refresh -s workflow"); \
	else \
		echo "$(RED)Error: GitHub CLI (gh) not installed. Install from: https://cli.github.com/$(NC)"; \
		exit 1; \
	fi

##@ Integration Testing

.PHONY: integration-test
integration-test: venv ## Run integration tests for monitoring releases
	@echo "$(GREEN)Running integration tests...$(NC)"
	@source .env 2>/dev/null || true && ./tests/integration/test_monitor_self.sh

.PHONY: test-monitor-self
test-monitor-self: venv ## Test monitoring this repository's releases
	@echo "$(GREEN)Testing monitor on release-monitor repository...$(NC)"
	@source .env 2>/dev/null || true && $(PYTHON) tests/integration/test_monitor_self.py

##@ Examples

.PHONY: example-json
example-json: venv ## Run monitoring and output JSON (example)
	@echo "$(GREEN)Example: JSON output$(NC)"
	@source .env && ./scripts/monitor.sh --config $(TEST_CONFIG) --format json | jq '.' || true

.PHONY: example-yaml
example-yaml: venv ## Run monitoring and output YAML (example)
	@echo "$(GREEN)Example: YAML output$(NC)"
	@source .env && ./scripts/monitor.sh --config $(TEST_CONFIG) --format yaml

.PHONY: example-new-releases
example-new-releases: venv ## Show only new releases (example)
	@echo "$(GREEN)Example: New releases only$(NC)"
	@source .env && ./scripts/monitor.sh --config $(TEST_CONFIG) --format json | \
		jq -r '.releases[] | "New release: \(.repository) \(.tag_name)"' || echo "No new releases found"

# Special targets
.PHONY: all
all: setup check ## Setup and run all checks

# Ensure virtual environment is activated for Python commands
$(PYTHON): venv

# Create directories if needed
$(shell mkdir -p logs tmp)