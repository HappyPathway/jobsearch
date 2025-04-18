#!/usr/bin/env python3
from google.cloud import storage
from google.cloud.exceptions import Conflict
import os
from logging_utils import setup_logging
from pathlib import Path
import json
import time
import random
import string
import subprocess

logger = setup_logging('setup_gcs')

def get_repo_identifier():
    """Get a unique identifier for this repository"""
    try:
        # Try to get the remote origin URL
        result = subprocess.run(
            ['git', 'config', '--get', 'remote.origin.url'],
            capture_output=True,
            text=True,
            check=True
        )
        url = result.stdout.strip()
        # Extract org/repo from URL and create a slug
        parts = url.rstrip('.git').split('/')
        return f"{parts[-2]}-{parts[-1]}".lower()
    except Exception as e:
        logger.warning(f"Could not get git remote URL: {e}")
        # Fallback to GitHub environment variables
        if os.getenv('GITHUB_REPOSITORY'):
            return os.getenv('GITHUB_REPOSITORY').replace('/', '-').lower()
        return 'jobsearch-default'

def generate_unique_bucket_name(prefix=None):
    """Generate a unique bucket name that follows GCS naming rules"""
    if prefix is None:
        prefix = get_repo_identifier()
    
    # Get current timestamp for uniqueness
    timestamp = hex(int(time.time()))[2:]
    
    # Generate 8 random chars
    random_chars = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    
    # Combine parts ensuring total length is under 63 chars
    max_prefix_len = 63 - len(timestamp) - len(random_chars) - 2  # -2 for hyphens
    if len(prefix) > max_prefix_len:
        prefix = prefix[:max_prefix_len]
    
    # Create bucket name with format: prefix-timestamp-random
    bucket_name = f"{prefix}-{timestamp}-{random_chars}".lower()
    
    return bucket_name

def setup_gcs_infrastructure():
    """Set up required GCS infrastructure for the job search application"""
    try:
        # Initialize GCS client
        client = storage.Client()
        
        # Check for existing config file in the repository
        config_path = Path(__file__).parent.parent / 'config' / 'gcs.json'
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = json.load(f)
                bucket_name = config.get('GCS_BUCKET_NAME')
                if bucket_name:
                    # Verify bucket exists and is accessible
                    try:
                        bucket = client.get_bucket(bucket_name)
                        logger.info(f"Using existing bucket: {bucket_name}")
                        return True
                    except Exception:
                        logger.warning(f"Configured bucket {bucket_name} not accessible, will create new one")
        
        # Generate a unique bucket name
        bucket_name = generate_unique_bucket_name()
        retries = 0
        max_retries = 3
        
        while retries < max_retries:
            try:
                # Create the bucket with standard settings
                bucket = client.create_bucket(
                    bucket_name,
                    location="us-central1"
                )
                # Set storage class after creation
                bucket.storage_class = "STANDARD"
                bucket.patch()
                logger.info(f"Created new bucket: {bucket_name}")
                break
            except Conflict:
                # If bucket name is taken, try another random name
                logger.info(f"Bucket name {bucket_name} already exists, trying another")
                bucket_name = generate_unique_bucket_name()
                retries += 1
                if retries == max_retries:
                    raise Exception("Failed to create bucket after maximum retries")
        
        # Set bucket lifecycle policy to save costs
        lifecycle_rules = [
            {
                "action": {"type": "Delete"},
                "condition": {
                    "age": 90,  # Delete old versions after 90 days
                    "isLive": False
                }
            }
        ]
        bucket.lifecycle_rules = lifecycle_rules
        
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
            
        logger.info("GCS infrastructure setup complete")
        print(f"GCS_BUCKET_NAME={bucket_name}")
        return True
        
    except Exception as e:
        logger.error(f"Error setting up GCS infrastructure: {str(e)}")
        raise

if __name__ == "__main__":
    setup_gcs_infrastructure()