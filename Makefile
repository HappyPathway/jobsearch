.PHONY: venv install clean init-db scrape-profile combine-summary parse-resume parse-cover-letter run help all generate-github-pages mark-applied test-integration

VENV_NAME=venv
PYTHON=$(VENV_NAME)/bin/python
PIP=$(VENV_NAME)/bin/pip

help:
	@echo "Available commands:"
	@echo "  make install         - Set up virtual environment and install dependencies"
	@echo "  make clean          - Remove virtual environment and cache files"
	@echo "  make init-db        - Initialize the database schema"
	@echo "  make scrape-profile - Scrape LinkedIn profile data"
	@echo "  make parse-resume   - Parse resume PDF"
	@echo "  make parse-cover-letter - Parse cover letter PDF"
	@echo "  make combine-summary- Generate combined profile summary"
	@echo "  make generate-github-pages - Generate GitHub Pages"
	@echo "  make generate-docs  - Generate documents for a specific job"
	@echo "  make mark-applied   - Mark a job as applied (requires URL)"
	@echo "  make run           - Run full application (scrape data and start UI)"
	@echo "  make all           - Collect all data (profile, resume, summary)"
	@echo "  make test-integration - Run integration tests"

venv:
	python3 -m venv $(VENV_NAME)

install:
	pip install -r requirements.txt
	pip install -e .

clean:
	rm -rf $(VENV_NAME)
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -delete
	find . -type f -name 'career_data.db' -delete

init-db: install
	$(PYTHON) scripts/init_db.py

scrape-profile:
	$(PYTHON) scripts/profile_scraper.py

parse-resume:
	$(PYTHON) scripts/resume_parser.py

parse-cover-letter:
	$(PYTHON) scripts/cover_letter_parser.py

combine-summary:
	$(PYTHON) scripts/combine_and_summarize.py

generate-github-pages:
	$(PYTHON) scripts/generate_github_pages.py

generate-docs: install
	$(PYTHON) scripts/generate_documents.py

mark-applied:
	@if [ -z "$(URL)" ]; then \
		echo "Error: URL parameter required. Usage: make mark-applied URL=<job_url> [STATUS=<status>] [NOTES='notes']"; \
		exit 1; \
	fi
	$(PYTHON) scripts/mark_job_applied.py "$(URL)" $(if $(STATUS),--status $(STATUS)) $(if $(NOTES),--notes "$(NOTES)")

test-integration:
	pytest tests/integration/

all: scrape-profile parse-resume combine-summary