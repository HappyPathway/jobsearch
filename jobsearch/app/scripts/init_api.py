#!/usr/bin/env python3
"""Initialize the API service environment and validate configuration."""

import os
import sys
from pathlib import Path
import shutil
import json
from typing import Optional

# Import from installed jobsearch package
from jobsearch.core.storage import GCSManager
from jobsearch.core.logging import setup_logging
from jobsearch.core.database import init_database

# Set up logging
logger = setup_logging('api_init')

def check_credentials() -> bool:
    """Verify that all required credentials are present."""
    required_vars = [
        'GOOGLE_APPLICATION_CREDENTIALS',
        'GEMINI_API_KEY',
        'SLACK_API_TOKEN',
        'SLACK_CHANNEL_ID',
        'MEDIUM_API_KEY'
    ]
    
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        logger.error(f"Missing required environment variables: {', '.join(missing)}")
        return False
        
    # Verify GCS credentials file exists
    creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    if not creds_path or not Path(creds_path).exists():
        logger.error(f"GCS credentials file not found at {creds_path}")
        return False
        
    return True

def setup_credentials_volume() -> bool:
    """Set up credentials volume for Docker deployment."""
    try:
        # Create credentials directory if it doesn't exist
        creds_dir = Path(__file__).parent.parent / 'credentials'
        creds_dir.mkdir(exist_ok=True)
        
        # Copy credentials file to volume location
        src_creds = Path(os.getenv('GOOGLE_APPLICATION_CREDENTIALS', ''))
        if src_creds.exists():
            dst_creds = creds_dir / 'credentials.json'
            shutil.copy2(src_creds, dst_creds)
            logger.info(f"Copied credentials to {dst_creds}")
            return True
        else:
            logger.error(f"Source credentials not found at {src_creds}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to set up credentials: {str(e)}")
        return False

def validate_database() -> bool:
    """Validate database connection and schema."""
    try:
        init_database()
        logger.info("Database initialization successful")
        return True
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        return False

def validate_storage() -> bool:
    """Validate GCS connection and configuration."""
    try:
        storage = GCSManager()
        storage.sync_db()  # This will test bucket access
        logger.info("GCS connection validated successfully")
        return True
    except Exception as e:
        logger.error(f"GCS validation failed: {str(e)}")
        return False

def main():
    """Main initialization routine."""
    success = True
    
    # Check environment variables
    if not check_credentials():
        success = False
        
    # Set up credentials for Docker
    if not setup_credentials_volume():
        success = False
        
    # Validate database
    if not validate_database():
        success = False
        
    # Validate storage
    if not validate_storage():
        success = False
        
    if success:
        logger.info("API service initialization completed successfully")
        return 0
    else:
        logger.error("API service initialization failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())