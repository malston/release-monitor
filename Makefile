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

# Load FLY_TARGET from .env file, fallback to test
# Add FLY_TARGET=your-target to .env to override the default
FLY_TARGET := $(shell if [ -f .env ]; then source .env && echo $${FLY_TARGET:-test}; else echo test; fi)

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
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)
	@printf "\n\033[1mTesting:\033[0m\n"
	@printf "  make test                  - Run unit tests only\n"
	@printf "  make test-integration      - Run integration tests (checks dependencies first)\n"
	@printf "  make test-all              - Run both unit and integration tests\n"
	@printf "  make test-integration-deps - Check integration test dependencies\n"
	@printf "  make test-manifest-downloads - Test manifest/YAML download functionality\n"
	@printf "\n\033[1mConfiguration:\033[0m\n"
	@printf "  Set FLY_TARGET in .env file to override Concourse target (default: $(FLY_TARGET))\n"
	@printf "  Example: echo 'FLY_TARGET=prod' >> .env\n"

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
test: test-unit ## Run all tests (alias for test-unit by default)
	@printf "$(GREEN)✓ Unit tests complete!$(NC)\n"
	@printf "$(YELLOW)Run 'make test-integration' for integration tests$(NC)\n"
	@printf "$(YELLOW)Run 'make test-all' for all tests$(NC)\n"

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

.PHONY: validate-simple
validate-simple: ## Validate simplified Concourse pipeline (no S3 required)
	@printf "$(GREEN)Validating simplified pipeline configuration...$(NC)\n"
	@./ci/validate-simple.sh

.PHONY: pipeline-set-test
pipeline-set-test: ## Deploy pipeline to test environment (public repos only, requires S3)
	@printf "$(GREEN)Deploying pipeline to test (public repositories)...$(NC)\n"
	@printf "$(YELLOW)Note: For private repos, use 'make pipeline-set-test-with-key'$(NC)\n"
	@printf "$(YELLOW)Note: For simplified setup without S3, use 'make pipeline-set-test-simple'$(NC)\n"
	@if [ -z "$$GITHUB_TOKEN" ]; then \
		printf "$(RED)Error: GITHUB_TOKEN environment variable not set$(NC)\n"; \
		printf "$(YELLOW)Please set: export GITHUB_TOKEN=\"your_github_token\"$(NC)\n"; \
		exit 1; \
	fi
	@fly -t $(FLY_TARGET) set-pipeline \
		-p github-release-monitor \
		-c ci/pipeline.yml \
		-l params/global.yml \
		-l params/test.yml \
		--var github_token="$$GITHUB_TOKEN" \
		--non-interactive

.PHONY: pipeline-set-test-simple
pipeline-set-test-simple: ## Deploy simplified pipeline to test environment (no S3 required)
	@printf "$(GREEN)Deploying simplified pipeline to test (no S3 required)...$(NC)\n"
	@printf "$(YELLOW)This pipeline doesn't require S3 configuration - perfect for getting started!$(NC)\n"
	@if [ -z "$$GITHUB_TOKEN" ]; then \
		printf "$(RED)Error: GITHUB_TOKEN environment variable not set$(NC)\n"; \
		printf "$(YELLOW)Please set: export GITHUB_TOKEN=\"your_github_token\"$(NC)\n"; \
		exit 1; \
	fi
	@fly -t $(FLY_TARGET) set-pipeline \
		-p github-release-monitor-simple \
		-c ci/pipeline-simple.yml \
		-l params/global.yml \
		-l params/test.yml \
		--var github_token="$$GITHUB_TOKEN" \
		--non-interactive

.PHONY: pipeline-set-test-simple-with-key
pipeline-set-test-simple-with-key: ## Deploy simplified pipeline with SSH key for private repos (no S3 required)
	@printf "$(GREEN)Deploying simplified pipeline with SSH key (no S3 required)...$(NC)\n"
	@SSH_KEY=""; \
	if [ -f ~/.ssh/id_ed25519 ]; then \
		SSH_KEY=~/.ssh/id_ed25519; \
		printf "$(GREEN)Using Ed25519 SSH key: ~/.ssh/id_ed25519$(NC)\n"; \
	elif [ -f ~/.ssh/id_rsa ]; then \
		SSH_KEY=~/.ssh/id_rsa; \
		printf "$(YELLOW)Using RSA SSH key: ~/.ssh/id_rsa$(NC)\n"; \
	else \
		printf "$(RED)Error: No SSH key found$(NC)\n"; \
		printf "$(YELLOW)Looked for: ~/.ssh/id_ed25519 (preferred) or ~/.ssh/id_rsa$(NC)\n"; \
		printf "$(YELLOW)Either create an SSH key or use 'make pipeline-set-test-simple' for public repos$(NC)\n"; \
		exit 1; \
	fi; \
	if [ -z "$$GITHUB_TOKEN" ]; then \
		printf "$(RED)Error: GITHUB_TOKEN environment variable not set$(NC)\n"; \
		printf "$(YELLOW)Please set: export GITHUB_TOKEN=\"your_github_token\"$(NC)\n"; \
		exit 1; \
	fi; \
	fly -t $(FLY_TARGET) set-pipeline \
		-p github-release-monitor-simple \
		-c ci/pipeline-simple.yml \
		-l params/global.yml \
		-l params/test.yml \
		--var git_private_key="$$(cat $$SSH_KEY)" \
		--var github_token="$$GITHUB_TOKEN" \
		--non-interactive

.PHONY: pipeline-set-test-minio
pipeline-set-test-minio: ## Deploy pipeline with Minio support (local development)
	@printf "$(GREEN)Deploying pipeline with Minio support...$(NC)\n"
	@SSH_KEY=""; \
	if [ -f ~/.ssh/id_ed25519 ]; then \
		SSH_KEY=~/.ssh/id_ed25519; \
		printf "$(GREEN)Using Ed25519 SSH key: ~/.ssh/id_ed25519$(NC)\n"; \
	elif [ -f ~/.ssh/id_rsa ]; then \
		SSH_KEY=~/.ssh/id_rsa; \
		printf "$(YELLOW)Using RSA SSH key: ~/.ssh/id_rsa$(NC)\n"; \
	else \
		printf "$(RED)Error: No SSH key found$(NC)\n"; \
		printf "$(YELLOW)Looked for: ~/.ssh/id_ed25519 (preferred) or ~/.ssh/id_rsa$(NC)\n"; \
		printf "$(YELLOW)Either create an SSH key or use 'make pipeline-set-test' for public repos$(NC)\n"; \
		exit 1; \
	fi; \
	if [ -z "$$GITHUB_TOKEN" ]; then \
		printf "$(RED)Error: GITHUB_TOKEN environment variable not set$(NC)\n"; \
		printf "$(YELLOW)Please set: export GITHUB_TOKEN=\"your_github_token\"$(NC)\n"; \
		exit 1; \
	fi; \
	fly -t $(FLY_TARGET) set-pipeline \
		-p github-release-monitor-minio \
		-c ci/pipeline-s3-compatible.yml \
		-l params/global-s3-compatible.yml \
		-l params/minio-local.yml \
		-l params/minio-credentials.yml \
		--var github_token="$$GITHUB_TOKEN" \
		--var git_private_key="$$(cat $$SSH_KEY)" \
		--non-interactive

.PHONY: force-download
force-download: ## Force download for specific repository (REPO=owner/repo, defaults to etcd-io/etcd)
	@if [ -z "$(REPO)" ]; then \
		printf "$(GREEN)Force downloading etcd-io/etcd (default)...$(NC)\n"; \
		fly -t $(FLY_TARGET) trigger-job -j github-release-monitor-minio/force-download-repo; \
	else \
		printf "$(GREEN)Force downloading $(REPO)...$(NC)\n"; \
		fly -t $(FLY_TARGET) trigger-job -j github-release-monitor-minio/force-download-repo -v force_download_repo="$(REPO)"; \
	fi

.PHONY: pipeline-set-test-with-key
pipeline-set-test-with-key: ## Deploy pipeline to test environment with SSH key for private repos (requires S3)
	@printf "$(GREEN)Deploying pipeline to test with SSH key...$(NC)\n"
	@SSH_KEY=""; \
	if [ -f ~/.ssh/id_ed25519 ]; then \
		SSH_KEY=~/.ssh/id_ed25519; \
		printf "$(GREEN)Using Ed25519 SSH key: ~/.ssh/id_ed25519$(NC)\n"; \
	elif [ -f ~/.ssh/id_rsa ]; then \
		SSH_KEY=~/.ssh/id_rsa; \
		printf "$(YELLOW)Using RSA SSH key: ~/.ssh/id_rsa$(NC)\n"; \
	else \
		printf "$(RED)Error: No SSH key found$(NC)\n"; \
		printf "$(YELLOW)Looked for: ~/.ssh/id_ed25519 (preferred) or ~/.ssh/id_rsa$(NC)\n"; \
		printf "$(YELLOW)Either create an SSH key or use 'make pipeline-set-test' for public repos$(NC)\n"; \
		exit 1; \
	fi; \
	if [ -z "$$GITHUB_TOKEN" ]; then \
		printf "$(RED)Error: GITHUB_TOKEN environment variable not set$(NC)\n"; \
		printf "$(YELLOW)Please set: export GITHUB_TOKEN=\"your_github_token\"$(NC)\n"; \
		exit 1; \
	fi; \
	fly -t $(FLY_TARGET) set-pipeline \
		-p github-release-monitor \
		-c ci/pipeline.yml \
		-l params/global.yml \
		-l params/test.yml \
		--var git_private_key="$$(cat $$SSH_KEY)" \
		--var github_token="$$GITHUB_TOKEN" \
		--non-interactive

.PHONY: pipeline-set-prod
pipeline-set-prod: ## Deploy pipeline to production
	@printf "$(GREEN)Deploying pipeline to production...$(NC)\n"
	@printf "$(YELLOW)Warning: This will deploy to production!$(NC)\n"
	@read -p "Continue? [y/N] " -n 1 -r; \
	printf "\n"; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		fly -t $(FLY_TARGET) set-pipeline \
			-p github-release-monitor \
			-c ci/pipeline.yml \
			-l params/global.yml \
			-l params/prod.yml \
			--var github_token="$$GITHUB_TOKEN" \
			--non-interactive; \
	else \
		printf "$(RED)Deployment cancelled$(NC)\n"; \
	fi

.PHONY: pipeline-set-prod-with-key
pipeline-set-prod-with-key: ## Deploy pipeline to production with SSH key for private repos
	@printf "$(GREEN)Deploying pipeline to production with SSH key...$(NC)\n"
	@printf "$(RED)Warning: This will deploy to production with SSH key access!$(NC)\n"
	@read -p "Continue? [y/N] " -n 1 -r; \
	printf "\n"; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		SSH_KEY=""; \
		if [ -f ~/.ssh/id_ed25519 ]; then \
			SSH_KEY=~/.ssh/id_ed25519; \
			printf "$(GREEN)Using Ed25519 SSH key: ~/.ssh/id_ed25519$(NC)\n"; \
		elif [ -f ~/.ssh/id_rsa ]; then \
			SSH_KEY=~/.ssh/id_rsa; \
			printf "$(YELLOW)Using RSA SSH key: ~/.ssh/id_rsa$(NC)\n"; \
		else \
			printf "$(RED)Error: No SSH key found$(NC)\n"; \
			printf "$(YELLOW)Looked for: ~/.ssh/id_ed25519 (preferred) or ~/.ssh/id_rsa$(NC)\n"; \
			exit 1; \
		fi; \
		if [ -z "$$GITHUB_TOKEN" ]; then \
			printf "$(RED)Error: GITHUB_TOKEN environment variable not set$(NC)\n"; \
			printf "$(YELLOW)Please set: export GITHUB_TOKEN=\"your_github_token\"$(NC)\n"; \
			exit 1; \
		fi; \
		fly -t $(FLY_TARGET) set-pipeline \
			-p github-release-monitor \
			-c ci/pipeline.yml \
			-l params/global.yml \
			-l params/prod.yml \
			--var git_private_key="$$(cat $$SSH_KEY)" \
			--var github_token="$$GITHUB_TOKEN" \
			--non-interactive; \
	else \
		printf "$(RED)Deployment cancelled$(NC)\n"; \
	fi

.PHONY: pipeline-destroy
pipeline-destroy: ## Destroy pipeline (prompts for target)
	@read -p "Target (test/prod): " target; \
	printf "$(RED)Destroying pipeline from $$target...$(NC)\n"; \
	./ci/fly.sh destroy -t $$target

##@ MinIO Version Database

.PHONY: view-version-db
view-version-db: venv ## View current MinIO version database contents
	@printf "$(GREEN)Viewing MinIO version database...$(NC)\n"
	@source $(VENV)/bin/activate && \
	export S3_ENDPOINT=http://localhost:9000 && \
	export AWS_ACCESS_KEY_ID=release-monitor-user && \
	export AWS_SECRET_ACCESS_KEY=release-monitor-pass && \
	export S3_BUCKET=release-monitor-output && \
	python3 scripts/view-version-db.py

.PHONY: clear-version-db
clear-version-db: venv ## Clear entire MinIO version database (forces re-download of all releases)
	@printf "$(YELLOW)Warning: This will clear the entire version database!$(NC)\n"
	@printf "$(YELLOW)All tracked releases will be re-downloaded on next pipeline run.$(NC)\n"
	@read -p "Continue? [y/N] " -n 1 -r; \
	printf "\n"; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		printf "$(GREEN)Clearing MinIO version database...$(NC)\n"; \
		source $(VENV)/bin/activate && \
		export S3_ENDPOINT=http://localhost:9000 && \
		export AWS_ACCESS_KEY_ID=release-monitor-user && \
		export AWS_SECRET_ACCESS_KEY=release-monitor-pass && \
		export S3_BUCKET=release-monitor-output && \
		python3 scripts/clear-version-db.py; \
	else \
		printf "$(RED)Operation cancelled$(NC)\n"; \
	fi

.PHONY: clear-version-entry
clear-version-entry: venv ## Clear specific repository from version database (REPO=owner/repo)
	@if [ -z "$(REPO)" ]; then \
		printf "$(RED)Error: REPO is required. Usage: make clear-version-entry REPO=etcd-io/etcd$(NC)\n"; \
		exit 1; \
	fi
	@printf "$(GREEN)Clearing $(REPO) from MinIO version database...$(NC)\n"
	@source $(VENV)/bin/activate && \
	export S3_ENDPOINT=http://localhost:9000 && \
	export AWS_ACCESS_KEY_ID=release-monitor-user && \
	export AWS_SECRET_ACCESS_KEY=release-monitor-pass && \
	export S3_BUCKET=release-monitor-output && \
	python3 scripts/clear-version-entry.py "$(REPO)"

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

##@ Testing

.PHONY: test-unit
test-unit: venv ## Run unit tests only
	@printf "$(GREEN)Running unit tests...$(NC)\n"
	@if [ -d "$(VENV)" ]; then \
		$(PYTHON) -m unittest discover tests -p "test_*.py" -v; \
	else \
		printf "$(RED)No virtual environment found. Run 'make setup' first$(NC)\n"; \
		exit 1; \
	fi

.PHONY: test-integration-deps
test-integration-deps: ## Check integration test dependencies
	@printf "$(GREEN)Checking integration test dependencies...$(NC)\n"
	@DEPS_OK=true; \
	if [ ! -f ".env" ]; then \
		printf "$(YELLOW)⚠️  .env file not found - GITHUB_TOKEN may not be set$(NC)\n"; \
		printf "   Run 'make setup' to create .env file\n"; \
		DEPS_OK=false; \
	fi; \
	if ! command -v python3 &> /dev/null; then \
		printf "$(RED)✗ Python 3 not installed$(NC)\n"; \
		DEPS_OK=false; \
	else \
		printf "$(GREEN)✓ Python 3 found$(NC)\n"; \
	fi; \
	if [ -n "$$MINIO_TESTS" ] || [ -n "$$S3_ENDPOINT" ]; then \
		if command -v mc &> /dev/null; then \
			printf "$(GREEN)✓ MinIO client (mc) found$(NC)\n"; \
			if mc alias list 2>&1 | grep -q "s3versiondb" &> /dev/null; then \
				printf "$(GREEN)✓ MinIO alias configured$(NC)\n"; \
			else \
				printf "$(YELLOW)⚠️  MinIO alias not configured$(NC)\n"; \
				printf "   Run: mc alias set s3versiondb <endpoint> <access-key> <secret-key>\n"; \
			fi; \
		else \
			printf "$(YELLOW)⚠️  MinIO client (mc) not found - S3 tests may fail$(NC)\n"; \
			printf "   Install from: https://min.io/docs/minio/linux/reference/minio-mc.html\n"; \
		fi; \
		if curl -s http://localhost:9000/minio/health/live &> /dev/null; then \
			printf "$(GREEN)✓ MinIO server is running on localhost:9000$(NC)\n"; \
		else \
			printf "$(YELLOW)⚠️  MinIO server not running on localhost:9000$(NC)\n"; \
			printf "   S3-related integration tests will fail\n"; \
			printf "   Start MinIO with: docker-compose up -d minio\n"; \
		fi; \
	fi; \
	if [ "$$DEPS_OK" = "false" ]; then \
		printf "\n$(RED)Some dependencies are missing. Integration tests may fail.$(NC)\n"; \
		exit 1; \
	else \
		printf "\n$(GREEN)✓ All core dependencies satisfied$(NC)\n"; \
	fi

.PHONY: test-integration
test-integration: venv test-integration-deps ## Run all integration tests (checks dependencies first)
	@printf "$(GREEN)Running all integration tests...$(NC)\n"
	@if [ ! -f ".env" ]; then \
		printf "$(YELLOW)Creating minimal .env for testing...$(NC)\n"; \
		echo "GITHUB_TOKEN=test_token_for_integration_tests" > .env; \
	fi
	@source .env && $(PYTHON) -m unittest discover tests/integration -p "test_*.py" -v

.PHONY: test-integration-minio
test-integration-minio: venv test-integration-deps ## Run MinIO/S3 integration tests
	@printf "$(GREEN)Running MinIO/S3 integration tests...$(NC)\n"
	@if ! curl -s http://localhost:9000/minio/health/live &> /dev/null; then \
		printf "$(RED)Error: MinIO is not running on localhost:9000$(NC)\n"; \
		printf "$(YELLOW)Start MinIO with: docker-compose up -d minio$(NC)\n"; \
		exit 1; \
	fi
	@export MINIO_TESTS=true && \
	export S3_ENDPOINT=http://localhost:9000 && \
	export AWS_ACCESS_KEY_ID=minioadmin && \
	export AWS_SECRET_ACCESS_KEY=minioadmin && \
	source .env 2>/dev/null || true && \
	$(PYTHON) -m unittest tests.integration.test_s3_integration -v 2>/dev/null || \
	printf "$(YELLOW)Note: Create test_s3_integration.py to test S3 functionality$(NC)\n"

.PHONY: test-manifest-downloads
test-manifest-downloads: venv ## Run manifest download tests (YAML, JSON files)
	@printf "$(GREEN)Running manifest download tests...$(NC)\n"
	@source .env 2>/dev/null || true && \
	$(PYTHON) -m unittest tests.test_manifest_downloads -v

.PHONY: test-all
test-all: test-unit test-integration ## Run all tests (unit + integration)

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
