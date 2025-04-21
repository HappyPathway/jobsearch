from google.cloud import storage
from pathlib import Path
import os
import json
from logging_utils import setup_logging
import shutil

logger = setup_logging('gcs_utils')

class GCSManager:
    def __init__(self):
        self.client = storage.Client()
        self.db_blob_name = 'career_data.db'
        self.local_db_path = Path(__file__).parent.parent / 'career_data.db'
        self.config_path = Path(__file__).parent.parent / 'config' / 'gcs.json'
        self.bucket_name = self._get_bucket_name()
        self.bucket = self.client.bucket(self.bucket_name)
    
    def _get_bucket_name(self):
        """Get bucket name from config file"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    if config.get('GCS_BUCKET_NAME'):
                        return config['GCS_BUCKET_NAME']
            
            raise ValueError("GCS configuration not found. Please run system initialization first.")
            
        except Exception as e:
            logger.error(f"Error getting bucket name: {str(e)}")
            raise

    def _ensure_local_dir(self, local_path):
        """Ensure local directory exists"""
        local_path.parent.mkdir(parents=True, exist_ok=True)

    def download_db(self):
        """Download the database file from GCS"""
        try:
            blob = self.bucket.blob(self.db_blob_name)
            if not blob.exists():
                logger.info("No existing database in GCS, will create new one")
                return False
                
            logger.info("Downloading database from GCS")
            blob.download_to_filename(self.local_db_path)
            return True
        except Exception as e:
            logger.error(f"Error downloading database: {str(e)}")
            return False
    
    def upload_db(self):
        """Upload the database file to GCS"""
        try:
            if not self.local_db_path.exists():
                logger.error("No local database file to upload")
                return False
                
            logger.info("Uploading database to GCS")
            blob = self.bucket.blob(self.db_blob_name)
            blob.upload_from_filename(self.local_db_path)
            return True
        except Exception as e:
            logger.error(f"Error uploading database: {str(e)}")
            return False

    def sync_db(self):
        """Ensure local and GCS databases are in sync"""
        return self.download_db()

    def upload_file(self, local_path, gcs_path):
        """Upload a file to GCS
        
        Args:
            local_path (Path): Local file path
            gcs_path (str): GCS path (e.g. 'applications/2025-04-20/resume.pdf')
        """
        try:
            if not local_path.exists():
                logger.error(f"Local file not found: {local_path}")
                return False
            
            logger.info(f"Uploading {local_path} to GCS at {gcs_path}")
            blob = self.bucket.blob(gcs_path)
            blob.upload_from_filename(str(local_path))
            return True
        except Exception as e:
            logger.error(f"Error uploading file to GCS: {str(e)}")
            return False

    def download_file(self, gcs_path, local_path):
        """Download a file from GCS
        
        Args:
            gcs_path (str): GCS path (e.g. 'applications/2025-04-20/resume.pdf')
            local_path (Path): Local file path
        """
        try:
            blob = self.bucket.blob(gcs_path)
            if not blob.exists():
                logger.error(f"File not found in GCS: {gcs_path}")
                return False
            
            logger.info(f"Downloading {gcs_path} from GCS to {local_path}")
            self._ensure_local_dir(local_path)
            blob.download_to_filename(str(local_path))
            return True
        except Exception as e:
            logger.error(f"Error downloading file from GCS: {str(e)}")
            return False

    def list_files(self, prefix=None):
        """List files in GCS bucket
        
        Args:
            prefix (str, optional): Filter files by prefix
        Returns:
            list: List of blob names
        """
        try:
            return [blob.name for blob in self.bucket.list_blobs(prefix=prefix)]
        except Exception as e:
            logger.error(f"Error listing files in GCS: {str(e)}")
            return []

    def file_exists(self, gcs_path):
        """Check if a file exists in GCS
        
        Args:
            gcs_path (str): GCS path to check
        Returns:
            bool: True if file exists
        """
        try:
            blob = self.bucket.blob(gcs_path)
            return blob.exists()
        except Exception as e:
            logger.error(f"Error checking file existence in GCS: {str(e)}")
            return False

    def delete_file(self, gcs_path):
        """Delete a file from GCS
        
        Args:
            gcs_path (str): GCS path to delete
        Returns:
            bool: True if deletion was successful
        """
        try:
            blob = self.bucket.blob(gcs_path)
            if blob.exists():
                blob.delete()
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting file from GCS: {str(e)}")
            return False

# Global instance
gcs = GCSManager()