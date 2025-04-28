import subprocess
import os
import pytest
import logging
import sys
import shutil
import json
from pathlib import Path
from google.cloud import storage

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger("integration-test")

logger.info("[MODULE] test_system_workflow.py loaded.")

# Initialize GCS for testing
config_path = Path(os.path.dirname(__file__)).parent.parent / 'config' / 'gcs.json'
client = storage.Client()

# Get bucket name from config
with open(config_path, 'r') as f:
    config = json.load(f)
    bucket_name = config['GCS_BUCKET_NAME']

bucket = client.bucket(bucket_name)
logger.info(f"Using GCS bucket: {bucket_name}")

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
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

def setup_test_environment():
    """Setup test directories and files"""
    # Create test directories
    base_dir = Path(__file__).parent.parent.parent
    strategies_dir = base_dir / 'strategies'
    test_data_dir = base_dir / 'tests' / 'data' / 'strategies'
    
    # Ensure directories exist
    strategies_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy test strategy file if it exists
    if test_data_dir.exists():
        for strategy_file in test_data_dir.glob('strategy_*.md'):
            shutil.copy2(strategy_file, strategies_dir)

def test_full_system_workflow():
    """Test the complete system workflow"""
    try:
        setup_test_environment()
        
        logger.info("1. Initializing the database...")
        result = subprocess.run(['python3', '-m', 'jobsearch.core.setup_storage', 'init'], 
                              cwd=WORKSPACE_ROOT, capture_output=True)
        assert result.returncode == 0, f"Database initialization failed: {result.stderr.decode()}"
        assert os.path.exists(DB_PATH), "Database was not created."
        logger.info("Database initialized.")

        logger.info("2. Parsing LinkedIn profile...")
        result = subprocess.run(['python3', '-m', 'jobsearch.features.profile_management.scraper'], 
                              cwd=WORKSPACE_ROOT, capture_output=True)
        assert result.returncode == 0, f"Profile scraper failed: {result.stderr.decode()}"
        logger.info("LinkedIn profile parsed.")

        logger.info("3. Parsing resume...")
        result = subprocess.run(['python3', '-m', 'jobsearch.features.profile_management.resume_parser'], 
                              cwd=WORKSPACE_ROOT, capture_output=True)
        assert result.returncode == 0, f"Resume parser failed: {result.stderr.decode()}"
        logger.info("Resume parsed.")

        logger.info("4. Parsing cover letter...")
        result = subprocess.run(['python3', '-m', 'jobsearch.features.profile_management.cover_letter_parser'], 
                              cwd=WORKSPACE_ROOT, capture_output=True)
        assert result.returncode == 0, f"Cover letter parser failed: {result.stderr.decode()}"
        logger.info("Cover letter parsed.")

        logger.info("5. Combining and summarizing profile data...")
        result = subprocess.run(['python3', '-m', 'jobsearch.features.profile_management.summarizer'], 
                              cwd=WORKSPACE_ROOT, capture_output=True)
        assert result.returncode == 0, f"Profile summarizer failed: {result.stderr.decode()}"
        logger.info("Profile data combined and summarized.")

        logger.info("6. Running job strategy (generates documents)...")
        result = subprocess.run(['python3', '-m', 'jobsearch.features.job_search.strategy'], 
                              cwd=WORKSPACE_ROOT, capture_output=True)
        
        # For CI environments, we might not have all PDF generation dependencies
        # So we check if this is a WeasyPrint dependency error and skip if needed
        if result.returncode != 0:
            stderr = result.stderr.decode()
            if 'OSError: cannot load library' in stderr and 'libgobject' in stderr:
                logger.warning("WeasyPrint dependencies missing - PDF generation skipped in this environment")
                logger.warning("This is expected in some CI environments without system libraries")
                pytest.skip("WeasyPrint dependencies not available")
            else:
                assert result.returncode == 0, f"Job strategy failed: {stderr}"
        
        assert os.path.exists(os.path.join(LOGS_DIR, 'job_strategy.log'))
        logger.info("Job strategy executed.")

        logger.info("7. Checking for generated strategy files in GCS...")
        strategy_files = list(bucket.list_blobs(prefix='strategies/'))
        strategy_files_list = [blob.name for blob in strategy_files]
        assert any(name.endswith('.md') for name in strategy_files_list), "No strategy files found in GCS."
        logger.info(f"Found strategy files in GCS: {strategy_files_list}")

        # We only check for application documents if the job_strategy.py succeeded
        # as these might not be generated in environments without PDF support
        if result.returncode == 0:
            logger.info("8. Checking for generated application documents in GCS...")
            application_files = list(bucket.list_blobs(prefix='applications/'))
            application_files_list = [blob.name for blob in application_files]
            assert any('resume' in name or 'cover_letter' in name for name in application_files_list), "No application documents found in GCS."
            logger.info(f"Found application documents in GCS: {application_files_list}")
    finally:
        # No local cleanup needed since we're using GCS
        pass