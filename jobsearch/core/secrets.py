"""Secure secrets management using Google Secret Manager."""
import os
from typing import Optional
from google.cloud import secretmanager
from jobsearch.core.logging import setup_logging

logger = setup_logging('secrets')

class SecretManager:
    """Manages secure access to application secrets."""
    
    def __init__(self):
        self._client = secretmanager.SecretManagerServiceClient()
        self._project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
        if not self._project_id:
            raise ValueError("GOOGLE_CLOUD_PROJECT environment variable not set")
            
        self._cache = {}
    
    def _get_secret_path(self, secret_name: str) -> str:
        """Get the full path to a secret.
        
        Args:
            secret_name: Name of the secret
            
        Returns:
            Full path to the secret in Secret Manager
        """
        return f"projects/{self._project_id}/secrets/{secret_name}/versions/latest"
    
    def get_secret(self, secret_name: str, use_cache: bool = True) -> Optional[str]:
        """Get a secret value from Secret Manager.
        
        Args:
            secret_name: Name of the secret
            use_cache: Whether to use cached values
            
        Returns:
            Secret value, or None if not found
        """
        try:
            # Check cache first
            if use_cache and secret_name in self._cache:
                return self._cache[secret_name]
            
            # Get from Secret Manager
            path = self._get_secret_path(secret_name)
            response = self._client.access_secret_version(request={"name": path})
            secret = response.payload.data.decode("UTF-8")
            
            # Update cache
            if use_cache:
                self._cache[secret_name] = secret
                
            return secret
            
        except Exception as e:
            logger.error(f"Error accessing secret {secret_name}: {str(e)}")
            return None

    def clear_cache(self):
        """Clear the secrets cache."""
        self._cache.clear()

# Global instance
secret_manager = SecretManager()
