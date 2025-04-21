#!/usr/bin/env python3
"""Script to migrate secrets from .env and GitHub to Google Secret Manager."""
import os
from pathlib import Path
from secrets_manager import secrets
from logging_utils import setup_logging
import json
import sys

logger = setup_logging('migrate_secrets')

def load_github_secrets():
    """Load GitHub secrets from a JSON file if provided."""
    github_secrets_path = Path(__file__).resolve().parent.parent / 'github_secrets.json'
    if not github_secrets_path.exists():
        logger.warning("No github_secrets.json file found. Skipping GitHub secrets migration.")
        return {}
        
    with open(github_secrets_path) as f:
        return json.load(f)

def main():
    """Main entry point for secrets migration."""
    try:
        # Migrate .env secrets
        logger.info("Migrating secrets from .env file...")
        if secrets.migrate_env_secrets():
            logger.info("Successfully migrated secrets from .env file")
        else:
            logger.error("Some secrets failed to migrate from .env file")
            
        # Migrate GitHub secrets
        logger.info("Migrating secrets from GitHub...")
        github_secrets = load_github_secrets()
        for name, value in github_secrets.items():
            if secrets.create_secret(name, value):
                logger.info(f"Successfully migrated GitHub secret: {name}")
            else:
                logger.error(f"Failed to migrate GitHub secret: {name}")
                
        logger.info("Migration complete!")
        return 0
        
    except Exception as e:
        logger.error(f"Error during secrets migration: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())