import subprocess
import os
import pytest
import logging
import sys

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger("integration-test")

logger.info("[MODULE] test_system_workflow.py loaded.")

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
SCRIPTS_DIR = os.path.join(WORKSPACE_ROOT, 'scripts')
DB_PATH = os.path.join(WORKSPACE_ROOT, 'career_data.db')
LOGS_DIR = os.path.join(WORKSPACE_ROOT, 'logs')

@pytest.fixture(scope="module", autouse=True)
def cleanup_generated_files():
    logger.info("[FIXTURE] cleanup_generated_files running.")
    yield
    # Clean up logs and generated files
    for log_file in os.listdir(LOGS_DIR):
        if log_file.endswith('.log'):
            os.remove(os.path.join(LOGS_DIR, log_file))


def test_full_system_workflow():
    logger.info("1. Initializing the database...")
    result = subprocess.run(['python3', 'init_db.py'], cwd=SCRIPTS_DIR, capture_output=True)
    assert result.returncode == 0, f"init_db.py failed: {result.stderr.decode()}"
    assert os.path.exists(DB_PATH), "Database was not created."
    logger.info("Database initialized.")

    logger.info("2. Parsing LinkedIn profile...")
    result = subprocess.run(['python3', 'profile_scraper.py'], cwd=SCRIPTS_DIR, capture_output=True)
    assert result.returncode == 0, f"profile_scraper.py failed: {result.stderr.decode()}"
    logger.info("LinkedIn profile parsed.")

    logger.info("3. Parsing resume...")
    result = subprocess.run(['python3', 'resume_parser.py'], cwd=SCRIPTS_DIR, capture_output=True)
    assert result.returncode == 0, f"resume_parser.py failed: {result.stderr.decode()}"
    logger.info("Resume parsed.")

    logger.info("4. Parsing cover letter...")
    result = subprocess.run(['python3', 'cover_letter_parser.py'], cwd=SCRIPTS_DIR, capture_output=True)
    assert result.returncode == 0, f"cover_letter_parser.py failed: {result.stderr.decode()}"
    logger.info("Cover letter parsed.")

    logger.info("5. Combining and summarizing profile data...")
    result = subprocess.run(['python3', 'combine_and_summarize.py'], cwd=SCRIPTS_DIR, capture_output=True)
    assert result.returncode == 0, f"combine_and_summarize.py failed: {result.stderr.decode()}"
    logger.info("Profile data combined and summarized.")

    logger.info("6. Running job strategy (generates documents)...")
    result = subprocess.run(['python3', 'job_strategy.py'], cwd=SCRIPTS_DIR, capture_output=True)
    
    # For CI environments, we might not have all PDF generation dependencies
    # So we check if this is a WeasyPrint dependency error and skip if needed
    if result.returncode != 0:
        stderr = result.stderr.decode()
        if 'OSError: cannot load library' in stderr and 'libgobject' in stderr:
            logger.warning("WeasyPrint dependencies missing - PDF generation skipped in this environment")
            logger.warning("This is expected in some CI environments without system libraries")
            pytest.skip("WeasyPrint dependencies not available")
        else:
            assert result.returncode == 0, f"job_strategy.py failed: {stderr}"
    
    assert os.path.exists(os.path.join(LOGS_DIR, 'job_strategy.log'))
    logger.info("Job strategy executed.")

    logger.info("7. Checking for generated strategy files...")
    strategies_dir = os.path.join(WORKSPACE_ROOT, 'strategies')
    strategy_files = [f for f in os.listdir(strategies_dir) if f.startswith('strategy_')]
    assert strategy_files, "No strategy files generated."
    logger.info(f"Found strategy files: {strategy_files}")

    # We only check for application directories if the job_strategy.py succeeded
    # as these might not be generated in environments without PDF support
    if result.returncode == 0:
        logger.info("8. Checking for generated application directories (documents)...")
        applications_dir = os.path.join(WORKSPACE_ROOT, 'applications')
        app_dirs = [d for d in os.listdir(applications_dir) if os.path.isdir(os.path.join(applications_dir, d))]
        assert app_dirs, "No application directories (documents) generated."
        logger.info(f"Found application directories: {app_dirs}")