from google.cloud import storage
from pathlib import Path
import os
import json
from utils import setup_logging

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

# Global instance
gcs = GCSManager()