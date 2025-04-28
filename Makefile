.PHONY: venv install install-dev test lint clean init-db combine-summary parse-resume parse-cover-letter run help all generate-github-pages mark-applied test-integration gh-strategy-cleanup gh-generate-docs gh-pages gh-test gh-init gh-job-strategy gh-profile-update slack-list-channels search-jobs generate-strategy generate-docs-for-jobs generate-strategy-from-file job-workflow daily-workflow full-workflow job-search-and-docs sync-and-publish force-unlock terraform-init terraform-plan terraform-apply terraform-destroy migrate-db clean-db setup-storage

PYTHON_VERSION ?= 3.12
VENV_NAME=venv
PYTHON=$(VENV_NAME)/bin/python
PIP=$(VENV_NAME)/bin/pip
PYTHONPATH=PYTHONPATH="$(shell pwd):$(shell pwd)/jobsearch"

# Module paths
JOBSEARCH_MODULE=jobsearch
FEATURES_MODULE=$(JOBSEARCH_MODULE).features

help:
	@echo "Available commands:"
	@echo "  make install         - Set up virtual environment and install dependencies"
	@echo "  make install-dev     - Install development dependencies"
	@echo "  make test            - Run tests"
	@echo "  make lint            - Run code linting and type checks"
	@echo "  make clean          - Remove virtual environment and cache files"
	@echo "  make clean-db       - Remove database files locally and from GCS"
	@echo "  make init-db        - Initialize the database schema"
	@echo "  make setup-storage  - Initialize storage and database"

setup-storage:
	$(PYTHONPATH) python -m jobsearch.core.setup_storage init

venv:
	python$(PYTHON_VERSION) -m venv $(VENV_NAME)

install: venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	$(PIP) install -e .

install-dev:
	$(PIP) install -e ".[dev]"

test:
	pytest

lint:
	black $(JOBSEARCH_MODULE) tests
	isort $(JOBSEARCH_MODULE) tests
	mypy $(JOBSEARCH_MODULE) tests

clean:
	rm -rf $(VENV_NAME)
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -delete
	find . -type f -name 'career_data.db' -delete

clean-db: install
	@echo "Warning: This will completely remove the database file locally and from GCS"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo ""; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		rm -f career_data.db; \
		$(PYTHONPATH) $(PYTHON) -m $(JOBSEARCH_MODULE).core.storage clean-db; \
		echo "✅ Database files removed"; \
	fi

migrate-db: install
	$(PYTHONPATH) $(PYTHON) -m $(JOBSEARCH_MODULE).core.database migrate

init-db: install migrate-db
	$(PYTHONPATH) $(PYTHON) -m $(JOBSEARCH_MODULE).core.setup_storage init

force-unlock: install
	$(PYTHON) -m $(JOBSEARCH_MODULE).core.storage unlock $(if $(FORCE),--force)

scrape-profile: init-db
	$(PYTHON) -m $(FEATURES_MODULE).profile_management.scraper

parse-resume: init-db
	$(PYTHON) -m $(FEATURES_MODULE).profile_management.resume_parser

parse-cover-letter: init-db
	$(PYTHON) -m $(FEATURES_MODULE).profile_management.cover_letter_parser

combine-summary: scrape-profile parse-resume parse-cover-letter
	$(PYTHON) -m $(FEATURES_MODULE).profile_management.summarizer

generate-github-pages:
	$(PYTHON) -m $(FEATURES_MODULE).web_presence.github_pages

generate-docs: init-db
	$(PYTHON) -m $(FEATURES_MODULE).document_generation.generator

mark-applied: install
	@if [ -z "$(URL)" ]; then \
		echo "Error: URL parameter required. Usage: make mark-applied URL=<job_url> [STATUS=<status>] [NOTES='notes']"; \
		exit 1; \
	fi
	$(PYTHON) -m $(FEATURES_MODULE).job_search.tracker "$(URL)" $(if $(STATUS),--status $(STATUS)) $(if $(NOTES),--notes "$(NOTES)")
	$(MAKE) sync-and-publish

test-integration:
	PYTHONPATH="$(shell pwd):$(shell pwd)/jobsearch" pytest tests/integration/

all: scrape-profile parse-resume combine-summary

# Job Strategy targets
search-jobs: init-db
	$(PYTHONPATH) $(PYTHON) -m $(FEATURES_MODULE).job_search.search --search-only $(if $(JOB_LIMIT),--job-limit $(JOB_LIMIT))

generate-strategy: search-jobs
	$(PYTHONPATH) $(PYTHON) -m $(FEATURES_MODULE).job_search.strategy $(if $(JOB_LIMIT),--job-limit $(JOB_LIMIT)) $(if $(NO_SLACK),--no-slack)

generate-strategy-from-file: install
	$(PYTHONPATH) $(PYTHON) -m $(FEATURES_MODULE).job_search.strategy --strategy-only $(if $(JOB_FILE),--job-file $(JOB_FILE)) $(if $(NO_SLACK),--no-slack)

generate-docs-for-jobs: generate-strategy
	$(PYTHONPATH) $(PYTHON) -m $(FEATURES_MODULE).job_search.strategy --strategy-only --generate-documents $(if $(JOB_FILE),--job-file $(JOB_FILE))

# Orchestration targets (combined workflows)
job-workflow: sync-and-publish generate-strategy generate-docs-for-jobs
	@echo "✅ Completed job workflow: Generated strategy and documents for high-priority jobs"

daily-workflow: sync-and-publish job-workflow generate-github-pages
	@echo "✅ Completed daily workflow: Generated strategy, documents, and updated GitHub Pages"

full-workflow: job-workflow mark-applied generate-github-pages
	@echo "✅ Completed full workflow: Generated strategy, documents, updated applied status, and GitHub Pages"
	@echo "Note: Applied jobs must be specified via URL parameter"

job-search-and-docs: search-jobs generate-docs-for-jobs
	@echo "✅ Completed job search and document generation"

sync-and-publish: init-db generate-github-pages
	$(PYTHON) -m $(JOBSEARCH_MODULE).core.storage sync
	@echo "✅ Synced database with GCS and published GitHub Pages"

# GitHub Actions workflow targets
gh-strategy-cleanup:
	gh workflow run strategy-cleanup.yml

gh-generate-docs:
	gh workflow run document-generation.yml

gh-pages:
	gh workflow run github-pages.yml

gh-test:
	gh workflow run integration-tests.yml

gh-init:
	gh workflow run system-init.yml

gh-job-strategy:
	gh workflow run job-strategy.yml

gh-profile-update:
	gh workflow run profile-update.yml

# Run all GitHub Actions workflows in sequence
gh-all: gh-init gh-profile-update gh-job-strategy gh-generate-docs gh-pages gh-test gh-strategy-cleanup

# Infrastructure management targets
terraform-init:
	cd terraform && terraform init -upgrade

terraform-plan:
	cd terraform && terraform plan

terraform-apply: terraform-init
	@echo "Applying Terraform changes..."
	cd terraform && terraform apply -auto-approve

terraform-destroy:
	cd terraform && terraform destroy -auto-approve
