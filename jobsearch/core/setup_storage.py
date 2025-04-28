"""Setup script for Google Cloud Storage and database initialization."""
import os
import sys
import json
import time
import uuid
from pathlib import Path
from google.cloud import storage
from google.cloud.exceptions import NotFound
from typing import Optional, Dict, List

from jobsearch.core.logging import setup_logging  
from jobsearch.core.database import engine, Base
from jobsearch.core.monitoring import setup_monitoring
from jobsearch.core.schemas import StorageConfig
from jobsearch.core.secrets import secret_manager

# Initialize core components
logger = setup_logging('setup_storage')
monitoring = setup_monitoring('storage')

def init_database() -> bool:
    """Initialize SQLite database."""
    try:
        monitoring.increment('init_database')
        logger.info("Creating database tables")
        Base.metadata.create_all(engine)
        monitoring.track_success('init_database')
        return True
        
    except Exception as e:
        monitoring.track_error('init_database', str(e))
        logger.error(f"Error initializing database: {str(e)}")
        return False

def load_gcs_config() -> Optional[StorageConfig]:
    """Load GCS configuration from config file."""
    try:
        monitoring.increment('load_config')
        config_path = Path(__file__).parent.parent.parent / 'config' / 'gcs.json'
        
        if not config_path.exists():
            return None
            
        with open(config_path) as f:
            config_data = json.load(f)
            config = StorageConfig(**config_data)
            
        monitoring.track_success('load_config')
        return config
        
    except Exception as e:
        monitoring.track_error('load_config', str(e))
        logger.error(f"Error loading GCS config: {str(e)}")
        return None

def get_repo_identifier() -> str:
    """Get a unique identifier for this repository."""
    try:
        # Try to use the git remote URL first
        import git
        try:
            repo = git.Repo(search_parent_directories=True)
            remote_url = repo.remotes.origin.url
            return remote_url.split('/')[-1].replace('.git', '')
        except (git.InvalidGitRepositoryError, AttributeError):
            pass
    except ImportError:
        pass
        
    # Fall back to directory name
    return Path.cwd().name

def setup_environment() -> bool:
    """Set up environment variables from config."""
    try:
        monitoring.increment('setup_env')
        config = load_gcs_config()
        
        if not config:
            logger.warning("No GCS config found, skipping environment setup")
            return False
            
        os.environ['GCS_BUCKET_NAME'] = config.GCS_BUCKET_NAME
        
        monitoring.track_success('setup_env')
        return True
        
    except Exception as e:
        monitoring.track_error('setup_env', str(e))
        logger.error(f"Error setting up environment: {str(e)}")
        return False

def setup_gcs() -> bool:
    """Initialize Google Cloud Storage bucket."""
    try:
        monitoring.increment('setup_gcs')
        config_path = Path(__file__).parent.parent.parent / 'config' / 'gcs.json'
        
        # Initialize storage client with credentials from secret manager
        gcs_credentials = secret_manager.get_secret('GCS_CREDENTIALS')
        if not gcs_credentials:
            raise ValueError("GCS credentials not found in secret manager")
            
        client = storage.Client.from_service_account_info(json.loads(gcs_credentials))
        
        # Generate unique but deterministic bucket name
        repo_id = get_repo_identifier()
        bucket_name = f'jobsearch-{repo_id}-{str(uuid.uuid5(uuid.NAMESPACE_DNS, repo_id))}'
        bucket_name = bucket_name.lower()  # GCS bucket names must be lowercase
        
        try:
            bucket = client.get_bucket(bucket_name)
            logger.info(f"Using existing bucket: {bucket_name}")
        except NotFound:
            logger.info(f"Creating new bucket: {bucket_name}")
            bucket = client.create_bucket(bucket_name)
            
        # Enable versioning for backup/recovery
        bucket.versioning_enabled = True
        bucket.patch()
        
        # Store the bucket name in the repository config
        config_path.parent.mkdir(exist_ok=True)
        config = {
            "GCS_BUCKET_NAME": bucket_name,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "repository": get_repo_identifier()
        }
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
            
        monitoring.track_success('setup_gcs')
        logger.info("GCS infrastructure setup complete")
        return True
        
    except Exception as e:
        monitoring.track_error('setup_gcs', str(e))
        logger.error(f"Error setting up GCS infrastructure: {str(e)}")
        return False

def validate_setup() -> bool:
    """Validate storage setup configuration."""
    try:
        monitoring.increment('validate_setup')
        config = load_gcs_config()
        
        if not config:
            logger.error("No GCS configuration found")
            return False
            
        client = storage.Client()
        try:
            bucket = client.get_bucket(config.GCS_BUCKET_NAME)
            # Try a test upload
            test_blob = bucket.blob('test.txt')
            test_blob.upload_from_string('test')
            test_blob.delete()
            
        except Exception as e:
            logger.error(f"Error validating bucket access: {str(e)}")
            return False
            
        monitoring.track_success('validate_setup')
        logger.info("Storage setup validated successfully")
        return True
        
    except Exception as e:
        monitoring.track_error('validate_setup', str(e))
        logger.error(f"Error validating setup: {str(e)}")
        return False

def main() -> int:
    """Main entry point."""
    try:
        # Initialize core database
        if not init_database():
            logger.error("Database initialization failed")
            return 1
            
        # Set up GCS infrastructure
        if not setup_gcs():
            logger.error("GCS setup failed")
            return 1
            
        # Set up environment
        if not setup_environment():
            logger.warning("Environment setup failed but continuing")
            
        # Validate setup
        if not validate_setup():
            logger.error("Setup validation failed")
            return 1
            
        logger.info("Storage setup complete")
        return 0
        
    except Exception as e:
        logger.error(f"Unexpected error in storage setup: {str(e)}")
        return 1

if __name__ == '__main__':
    sys.exit(main())