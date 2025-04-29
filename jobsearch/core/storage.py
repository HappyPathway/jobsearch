"""Google Cloud Storage integration with monitoring.

This module provides a unified interface for interacting with Google Cloud Storage.
It handles file management, database synchronization, locking mechanisms,
and provides specialized methods for common operations used across the application.

Example:
    ```python
    from jobsearch.core.storage import gcs
    
    # Upload a file
    gcs.upload_file('local_path.txt', 'remote_path.txt')
    
    # Download a file
    gcs.download_file('remote_path.txt', 'local_path.txt')
    
    # Sync database
    gcs.sync_db()
    ```
"""
import os
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Union, Tuple
from google.cloud import storage
from google.cloud.exceptions import NotFound

from jobsearch.core.logging import setup_logging
from jobsearch.core.monitoring import setup_monitoring
from jobsearch.core.schemas import StorageConfig

# Initialize core components
logger = setup_logging('storage')
monitoring = setup_monitoring('storage')

class GCSManager:
    """Manages interaction with Google Cloud Storage.
    
    This class provides methods for:
    - Database synchronization with GCS
    - File upload and download operations
    - Locking mechanism for concurrent access control
    - Safe operations with retry logic
    - Application-specific file operations
    
    Attributes:
        client: Google Cloud Storage client
        bucket: GCS bucket instance
        db_blob_name: Name of the database file in GCS
        local_db_path: Path to the local database file
        db_lock_blob_name: Name of the lock file in GCS
        lock_retry_attempts: Number of attempts to acquire a lock
        lock_retry_delay: Delay between lock attempts in seconds
    """
    
    def __init__(self):
        """Initialize the GCS manager with default configuration."""
        self.client = storage.Client()
        self.db_blob_name = 'career_data.db'
        self.local_db_path = Path(__file__).parent.parent / 'career_data.db'
        self.config_path = Path(__file__).parent.parent / 'config' / 'gcs.json'
        self.bucket_name = self._get_bucket_name()
        self.bucket = self.client.bucket(self.bucket_name)
        self.db_lock_blob_name = 'career_data.db.lock'
        self.lock_retry_attempts = 50
        self.lock_retry_delay = 0.5  # seconds
        
        # Create bucket if it doesn't exist
        self._ensure_bucket()
        
    def _get_bucket_name(self) -> str:
        """Get bucket name from config file.
        
        Returns:
            The name of the GCS bucket to use
            
        Raises:
            FileNotFoundError: If the config file is not found
            KeyError: If the bucket_name is not in the config file
        """
        try:
            monitoring.increment('config_read')
            if not self.config_path.exists():
                raise FileNotFoundError("GCS config file not found")
                
            with open(self.config_path) as f:
                config = json.load(f)
                
            if 'bucket_name' not in config:
                raise KeyError("bucket_name not found in GCS config")
                
            monitoring.track_success('config_read')
            return config['bucket_name']
            
        except Exception as e:
            monitoring.track_error('config_read', str(e))
            logger.error(f"Error reading GCS config: {str(e)}")
            raise
            
    def _ensure_bucket(self):
        """Create bucket if it doesn't exist."""
        try:
            monitoring.increment('bucket_check')
            self.bucket = self.client.bucket(self.bucket_name)
            
            if not self.bucket.exists():
                logger.info(f"Creating bucket: {self.bucket_name}")
                self.bucket = self.client.create_bucket(self.bucket_name)
                
            monitoring.track_success('bucket_check')
                
        except Exception as e:
            monitoring.track_error('bucket_check', str(e))
            logger.error(f"Error checking/creating bucket: {str(e)}")
            raise
            
    def _ensure_local_dir(self, local_path: Path):
        """Ensure local directory exists."""
        local_path.parent.mkdir(parents=True, exist_ok=True)
            
    def download_db(self) -> bool:
        """Download the database file from GCS."""
        try:
            monitoring.increment('db_download')
            blob = self.bucket.blob(self.db_blob_name)
            
            if not blob.exists():
                logger.info("No existing database in GCS")
                if not self.local_db_path.exists():
                    self.local_db_path.touch()
                return False
                
            logger.info("Downloading database from GCS")
            self._ensure_local_dir(self.local_db_path)
            blob.download_to_filename(self.local_db_path)
            
            monitoring.track_success('db_download')
            return True
            
        except Exception as e:
            monitoring.track_error('db_download', str(e))
            logger.error(f"Error downloading database: {str(e)}")
            if not self.local_db_path.exists():
                self.local_db_path.touch()
            return False
            
    def upload_db(self) -> bool:
        """Upload the database file to GCS."""
        try:
            monitoring.increment('db_upload')
            if not self.local_db_path.exists():
                logger.error("No local database file to upload")
                return False
                
            logger.info("Uploading database to GCS")
            blob = self.bucket.blob(self.db_blob_name)
            blob.upload_from_filename(self.local_db_path)
            
            monitoring.track_success('db_upload')
            return True
            
        except Exception as e:
            monitoring.track_error('db_upload', str(e))
            logger.error(f"Error uploading database: {str(e)}")
            return False
            
    def acquire_lock(self) -> bool:
        """Acquire a lock on the database."""
        lock_blob = self.bucket.blob(self.db_lock_blob_name)
        
        for attempt in range(self.lock_retry_attempts):
            try:
                monitoring.increment('lock_acquire')
                if not lock_blob.exists():
                    # Create lock file
                    lock_blob.upload_from_string(
                        json.dumps({
                            'locked_at': datetime.now().isoformat(),
                            'process_id': os.getpid()
                        })
                    )
                    monitoring.track_success('lock_acquire')
                    return True
                    
                # Check if lock is stale
                try:
                    lock_data = json.loads(lock_blob.download_as_string())
                    locked_at = datetime.fromisoformat(lock_data['locked_at'])
                    age = (datetime.now() - locked_at).total_seconds()
                    
                    if age > 300:  # 5 minutes
                        logger.warning("Found stale lock, removing")
                        self.release_lock()
                        continue
                        
                except:
                    # If we can't read the lock file, assume it's corrupt
                    self.release_lock()
                    continue
                    
                # Wait before retrying
                logger.debug(f"Lock exists, waiting... (attempt {attempt + 1}/{self.lock_retry_attempts})")
                time.sleep(self.lock_retry_delay)
                
            except Exception as e:
                monitoring.track_error('lock_acquire', str(e))
                logger.error(f"Error acquiring lock: {str(e)}")
                return False
                
        logger.error("Failed to acquire lock after maximum attempts")
        return False
        
    def release_lock(self):
        """Release the database lock."""
        try:
            monitoring.increment('lock_release')
            lock_blob = self.bucket.blob(self.db_lock_blob_name)
            if lock_blob.exists():
                lock_blob.delete()
            monitoring.track_success('lock_release')
            
        except Exception as e:
            monitoring.track_error('lock_release', str(e))
            logger.error(f"Error releasing lock: {str(e)}")
            
    def force_unlock(self):
        """Force release of the database lock."""
        self.release_lock()
            
    def sync_db(self) -> bool:
        """Download database from GCS without lock management."""
        return self.download_db()
            
    def sync_and_upload_db(self) -> bool:
        """Sync local DB with GCS and upload changes."""
        if not self.acquire_lock():
            raise Exception("Could not acquire database lock")
            
        try:
            monitoring.increment('db_sync')
            self.sync_db()
            if self.local_db_path.exists():
                logger.info("Uploading database to GCS")
                blob = self.bucket.blob(self.db_blob_name)
                blob.upload_from_filename(self.local_db_path)
            monitoring.track_success('db_sync')
            return True
            
        except Exception as e:
            monitoring.track_error('db_sync', str(e))
            logger.error(f"Error syncing database: {str(e)}")
            return False
            
        finally:
            self.release_lock()
            
    def upload_file(self, local_path: Union[str, Path], gcs_path: str) -> bool:
        """Upload a file to GCS."""
        try:
            monitoring.increment('file_upload')
            local_path = Path(local_path)
            if not local_path.exists():
                logger.error(f"Local file not found: {local_path}")
                return False
                
            blob = self.bucket.blob(gcs_path)
            blob.upload_from_filename(str(local_path))
            
            monitoring.track_success('file_upload')
            return True
            
        except Exception as e:
            monitoring.track_error('file_upload', str(e))
            logger.error(f"Error uploading file: {str(e)}")
            return False
            
    def download_file(self, gcs_path: str, local_path: Union[str, Path]) -> bool:
        """Download a file from GCS."""
        try:
            monitoring.increment('file_download')
            local_path = Path(local_path)
            self._ensure_local_dir(local_path)
            
            blob = self.bucket.blob(gcs_path)
            if not blob.exists():
                logger.error(f"GCS file not found: {gcs_path}")
                return False
                
            blob.download_to_filename(str(local_path))
            
            monitoring.track_success('file_download')
            return True
            
        except Exception as e:
            monitoring.track_error('file_download', str(e))
            logger.error(f"Error downloading file: {str(e)}")
            return False
            
    def list_files(self, prefix: Optional[str] = None) -> List[str]:
        """List files in GCS bucket."""
        try:
            monitoring.increment('list_files')
            files = [blob.name for blob in self.bucket.list_blobs(prefix=prefix)]
            monitoring.track_success('list_files')
            return files
            
        except Exception as e:
            monitoring.track_error('list_files', str(e))
            logger.error(f"Error listing files: {str(e)}")
            return []
            
    def file_exists(self, gcs_path: str) -> bool:
        """Check if a file exists in GCS."""
        try:
            monitoring.increment('file_check')
            blob = self.bucket.blob(gcs_path)
            exists = blob.exists()
            monitoring.track_success('file_check')
            return exists
            
        except Exception as e:
            monitoring.track_error('file_check', str(e))
            logger.error(f"Error checking file existence: {str(e)}")
            return False
            
    def delete_file(self, gcs_path: str) -> bool:
        """Delete a file from GCS."""
        try:
            monitoring.increment('file_delete')
            blob = self.bucket.blob(gcs_path)
            if blob.exists():
                blob.delete()
            monitoring.track_success('file_delete')
            return True
            
        except Exception as e:
            monitoring.track_error('file_delete', str(e))
            logger.error(f"Error deleting file: {str(e)}")
            return False
            
    def read_application_files(self, application_date: str, company: str, role: str) -> Dict[str, str]:
        """Read application files from GCS."""
        try:
            monitoring.increment('read_application')
            base_path = f'applications/{application_date}_{company}_{role}'
            files = {}
            
            for blob in self.bucket.list_blobs(prefix=base_path):
                files[blob.name.split('/')[-1]] = blob.download_as_text()
                
            monitoring.track_success('read_application')
            return files
            
        except Exception as e:
            monitoring.track_error('read_application', str(e))
            logger.error(f"Error reading application files: {str(e)}")
            return {}
            
    def read_strategy(self, strategy_date: str) -> Tuple[Optional[str], Optional[str]]:
        """Read a strategy file from GCS."""
        try:
            monitoring.increment('read_strategy')
            md_path = f'strategies/strategy_{strategy_date}.md'
            txt_path = f'strategies/strategy_{strategy_date}.txt'
            
            md_blob = self.bucket.blob(md_path)
            txt_blob = self.bucket.blob(txt_path)
            
            if not md_blob.exists() or not txt_blob.exists():
                logger.error(f"Strategy files for {strategy_date} not found")
                return None, None
                
            monitoring.track_success('read_strategy')
            return (
                md_blob.download_as_text(),
                txt_blob.download_as_text()
            )
            
        except Exception as e:
            monitoring.track_error('read_strategy', str(e))
            logger.error(f"Error reading strategy files: {str(e)}")
            return None, None
            
    def safe_upload(self, content: Union[str, bytes], gcs_path: str) -> bool:
        """Safely upload content to GCS with retry logic."""
        for attempt in range(3):
            try:
                monitoring.increment('safe_upload')
                blob = self.bucket.blob(gcs_path)
                if isinstance(content, str):
                    blob.upload_from_string(content)
                else:
                    blob.upload_from_string(content, content_type='application/octet-stream')
                    
                monitoring.track_success('safe_upload')
                return True
                
            except Exception as e:
                logger.warning(f"Upload attempt {attempt + 1} failed: {str(e)}")
                time.sleep(1)
                
        monitoring.track_error('safe_upload', "Max retries exceeded")
        logger.error(f"Failed to upload {gcs_path} after 3 attempts")
        return False
            
    def safe_download(self, gcs_path: str) -> Optional[Union[str, bytes]]:
        """Safely download content from GCS with retry logic."""
        for attempt in range(3):
            try:
                monitoring.increment('safe_download')
                blob = self.bucket.blob(gcs_path)
                if not blob.exists():
                    return None
                    
                try:
                    content = blob.download_as_text()
                except UnicodeDecodeError:
                    content = blob.download_as_bytes()
                    
                monitoring.track_success('safe_download')
                return content
                
            except Exception as e:
                logger.warning(f"Download attempt {attempt + 1} failed: {str(e)}")
                time.sleep(1)
                
        monitoring.track_error('safe_download', "Max retries exceeded")
        logger.error(f"Failed to download {gcs_path} after 3 attempts")
        return None

# Global instance
gcs = GCSManager()