"""Centralized secrets management using Google Secret Manager."""
import os
from google.cloud import secretmanager
from google.api_core import retry
from pathlib import Path
import json
from logging_utils import setup_logging

logger = setup_logging('secrets_manager')

class SecretsManager:
    """Handles all interactions with Google Secret Manager."""
    
    def __init__(self):
        self.client = secretmanager.SecretManagerServiceClient()
        self.project_id = self._get_project_id()
        
    def _get_project_id(self):
        """Get Google Cloud project ID from config or environment."""
        # Try to get from environment first
        project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
        if project_id:
            return project_id
            
        # Try to get from config/gcs.json
        config_path = Path(__file__).resolve().parent.parent / 'config' / 'gcs.json'
        if config_path.exists():
            with open(config_path) as f:
                config = json.load(f)
                if 'project_id' in config:
                    return config['project_id']
                    
        raise ValueError("Could not determine Google Cloud project ID")
    
    def _get_secret_path(self, secret_name):
        """Construct the full path for a secret."""
        return f"projects/{self.project_id}/secrets/{secret_name}/versions/latest"
    
    @retry.Retry()
    def get_secret(self, secret_name):
        """Get a secret value from Secret Manager."""
        try:
            name = self._get_secret_path(secret_name)
            response = self.client.access_secret_version(request={"name": name})
            return response.payload.data.decode("UTF-8")
        except Exception as e:
            logger.error(f"Error accessing secret {secret_name}: {str(e)}")
            # Fall back to environment variable if secret not in Secret Manager
            return os.getenv(secret_name)
    
    @retry.Retry()
    def create_secret(self, secret_name, secret_value):
        """Create a new secret in Secret Manager."""
        try:
            parent = f"projects/{self.project_id}"
            
            # Create the secret object
            self.client.create_secret(
                request={
                    "parent": parent,
                    "secret_id": secret_name,
                    "secret": {
                        "replication": {
                            "automatic": {},
                        },
                    },
                }
            )
            
            # Add the secret version
            self.client.add_secret_version(
                request={
                    "parent": f"{parent}/secrets/{secret_name}",
                    "payload": {"data": secret_value.encode("UTF-8")},
                }
            )
            
            logger.info(f"Successfully created secret: {secret_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating secret {secret_name}: {str(e)}")
            return False
    
    def migrate_env_secrets(self):
        """Migrate secrets from .env file to Secret Manager."""
        env_path = Path(__file__).resolve().parent.parent / '.env'
        if not env_path.exists():
            logger.warning("No .env file found to migrate")
            return False
            
        success = True
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                    
                try:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip("'").strip('"')
                    
                    if not self.create_secret(key, value):
                        success = False
                        
                except ValueError:
                    logger.warning(f"Skipping invalid line in .env: {line}")
                    success = False
                    
        return success

# Create a singleton instance
secrets = SecretsManager()