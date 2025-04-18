.PHONY: venv install clean init-db scrape-profile combine-summary parse-resume run-ui run help all generate-docs mark-applied

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
	@echo "  make combine-summary- Generate combined profile summary"
	@echo "  make generate-docs  - Generate documents for a specific job"
	@echo "  make mark-applied   - Mark a job as applied (requires URL)"
	@echo "  make run-ui         - Start the web interface"
	@echo "  make run           - Run full application (scrape data and start UI)"
	@echo "  make all           - Collect all data (profile, resume, summary)"

venv:
	python3 -m venv $(VENV_NAME)

install: venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

clean:
	rm -rf $(VENV_NAME)
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -delete
	find . -type f -name 'career_data.db' -delete

init-db: install
	$(PYTHON) scripts/init_db.py

scrape-profile: init-db
	$(PYTHON) scripts/profile_scraper.py

parse-resume: init-db
	$(PYTHON) scripts/resume_parser.py

combine-summary: init-db
	$(PYTHON) scripts/combine_and_summarize.py

generate-docs: install
	$(PYTHON) scripts/generate_documents.py

mark-applied:
	@if [ -z "$(URL)" ]; then \
		echo "Error: URL parameter required. Usage: make mark-applied URL=<job_url> [STATUS=<status>] [NOTES='notes']"; \
		exit 1; \
	fi
	$(PYTHON) scripts/mark_job_applied.py "$(URL)" $(if $(STATUS),--status $(STATUS)) $(if $(NOTES),--notes "$(NOTES)")

run-ui: install
	$(PYTHON) scripts/career_ui.py

all: scrape-profile parse-resume combine-summary

run: all run-ui