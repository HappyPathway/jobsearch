"""Google Cloud Storage management utilities."""

from google.cloud import storage
from pathlib import Path
import json
import time
from .logging import logger

class GCSManager:
    """Manages interaction with Google Cloud Storage."""
    
    def __init__(self):
        self.client = storage.Client()
        self.db_blob_name = 'career_data.db'
        self.local_db_path = Path(__file__).parent.parent.parent / 'career_data.db'
        self.config_path = Path(__file__).parent.parent.parent / 'config' / 'gcs.json'
        self.bucket_name = self._get_bucket_name()
        self.bucket = self.client.bucket(self.bucket_name)
        self.db_lock_blob_name = 'career_data.db.lock'
        self.lock_retry_attempts = 50
        self.lock_retry_delay = 0.5  # seconds
    
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
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)

    def download_db(self):
        """Download the database file from GCS"""
        try:
            blob = self.bucket.blob(self.db_blob_name)
            self._ensure_local_dir(self.local_db_path)
            blob.download_to_filename(self.local_db_path)
            logger.info("Downloaded database from GCS")
            return True
        except Exception as e:
            logger.error(f"Error downloading database: {str(e)}")
            return False

    def upload_db(self):
        """Upload the database file to GCS"""
        try:
            if self.local_db_path.exists():
                blob = self.bucket.blob(self.db_blob_name)
                blob.upload_from_filename(self.local_db_path)
                logger.info("Uploaded database to GCS")
                return True
            return False
        except Exception as e:
            logger.error(f"Error uploading database: {str(e)}")
            return False

    def acquire_lock(self):
        """Acquire a lock for database operations"""
        attempt = 0
        while attempt < self.lock_retry_attempts:
            try:
                # Check if lock exists
                lock_blob = self.bucket.blob(self.db_lock_blob_name)
                
                if not lock_blob.exists():
                    # Create lock file
                    lock_data = {
                        'locked_at': time.time(),
                        'process_id': os.getpid()
                    }
                    lock_blob.upload_from_string(json.dumps(lock_data))
                    logger.debug("Lock acquired")
                    return True

                # Lock exists, check if it's stale
                try:
                    lock_content = json.loads(lock_blob.download_as_text())
                    lock_time = lock_content.get('locked_at', 0)
                    
                    # If lock is older than 5 minutes, consider it stale
                    if time.time() - lock_time > 300:
                        self.force_unlock()
                        continue
                    
                except:
                    # If we can't read the lock file, assume it's corrupt
                    self.release_lock()
                    continue

                # Wait before retrying
                logger.debug(f"Lock exists, waiting... (attempt {attempt + 1}/{self.lock_retry_attempts})")
                time.sleep(self.lock_retry_delay)
                attempt += 1
                
            except Exception as e:
                logger.error(f"Error acquiring lock: {str(e)}")
                return False

        logger.error("Failed to acquire lock after maximum attempts")
        return False

    def release_lock(self):
        """Release the database lock"""
        try:
            lock_blob = self.bucket.blob(self.db_lock_blob_name)
            if lock_blob.exists():
                lock_blob.delete()
            logger.debug("Lock released")
            return True
        except Exception as e:
            logger.error(f"Error releasing lock: {str(e)}")
            return False

    def force_unlock(self):
        """Force remove a lock (use with caution)"""
        return self.release_lock()

    def sync_db(self):
        """Download database from GCS without lock management"""
        return self.download_db()

    def sync_and_upload_db(self):
        """Sync local DB with GCS and upload changes"""
        if not self.acquire_lock():
            raise Exception("Could not acquire database lock")
        try:
            self.sync_db()
            if self.local_db_path.exists():
                logger.info("Uploading database to GCS")
                blob = self.bucket.blob(self.db_blob_name)
                blob.upload_from_filename(self.local_db_path)
        finally:
            self.release_lock()

    def upload_file(self, local_path, gcs_path):
        """Upload a file to GCS"""
        try:
            blob = self.bucket.blob(gcs_path)
            blob.upload_from_filename(local_path)
            logger.info(f"Uploaded {local_path} to {gcs_path}")
            return True
        except Exception as e:
            logger.error(f"Error uploading file: {str(e)}")
            return False

    def download_file(self, gcs_path, local_path):
        """Download a file from GCS"""
        try:
            blob = self.bucket.blob(gcs_path)
            self._ensure_local_dir(local_path)
            blob.download_to_filename(local_path)
            logger.info(f"Downloaded {gcs_path} to {local_path}")
            return True
        except Exception as e:
            logger.error(f"Error downloading file: {str(e)}")
            return False

    def list_files(self, prefix=None):
        """List files in GCS bucket"""
        try:
            return [blob.name for blob in self.bucket.list_blobs(prefix=prefix)]
        except Exception as e:
            logger.error(f"Error listing files: {str(e)}")
            return []

    def file_exists(self, gcs_path):
        """Check if a file exists in GCS"""
        try:
            blob = self.bucket.blob(gcs_path)
            return blob.exists()
        except Exception as e:
            logger.error(f"Error checking file existence: {str(e)}")
            return False

    def delete_file(self, gcs_path):
        """Delete a file from GCS"""
        try:
            blob = self.bucket.blob(gcs_path)
            blob.delete()
            logger.info(f"Deleted {gcs_path}")
            return True
        except Exception as e:
            logger.error(f"Error deleting file: {str(e)}")
            return False

    def read_application_files(self, application_date, company, role):
        """Read application files from GCS
        
        Args:
            application_date (str): Date in YYYY-MM-DD format
            company (str): Company name
            role (str): Role name
        Returns:
            dict: Dictionary of file contents by filename
        """
        try:
            base_path = f'applications/{application_date}_{company}_{role}'
            files = {}
            
            # List all files in the application directory
            for blob in self.bucket.list_blobs(prefix=base_path):
                files[blob.name.split('/')[-1]] = blob.download_as_text()
            
            return files
        except Exception as e:
            logger.error(f"Error reading application files: {str(e)}")
            return {}

    def read_strategy(self, strategy_date):
        """Read a strategy file from GCS
        
        Args:
            strategy_date (str): Date in YYYY-MM-DD format
        Returns:
            dict: Strategy data or None if not found
        """
        try:
            gcs_path = f'strategies/{strategy_date}_strategy.json'
            blob = self.bucket.blob(gcs_path)
            
            if blob.exists():
                return json.loads(blob.download_as_text())
            return None
            
        except Exception as e:
            logger.error(f"Error reading strategy: {str(e)}")
            return None

    def safe_upload(self, content, gcs_path):
        """Safely upload content to GCS with retries
        
        Args:
            content (str): Content to upload
            gcs_path (str): Path in GCS bucket
        Returns:
            bool: True if successful, False otherwise
        """
        max_retries = 3
        attempt = 0
        
        while attempt < max_retries:
            try:
                blob = self.bucket.blob(gcs_path)
                blob.upload_from_string(content)
                return True
            except Exception as e:
                logger.warning(f"Upload attempt {attempt + 1} failed: {str(e)}")
                attempt += 1
                time.sleep(1)
        
        logger.error(f"Failed to upload {gcs_path} after {max_retries} attempts")
        return False

    def safe_download(self, gcs_path):
        """Safely download content from GCS with retries
        
        Args:
            gcs_path (str): Path in GCS bucket
        Returns:
            str: File content or None if failed
        """
        max_retries = 3
        attempt = 0
        
        while attempt < max_retries:
            try:
                blob = self.bucket.blob(gcs_path)
                return blob.download_as_text()
            except Exception as e:
                logger.warning(f"Download attempt {attempt + 1} failed: {str(e)}")
                attempt += 1
                time.sleep(1)
        
        logger.error(f"Failed to download {gcs_path} after {max_retries} attempts")
        return None

# Global instance
gcs = GCSManager()