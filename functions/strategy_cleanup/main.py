from flask import Flask, request
import functions_framework
import sys
from pathlib import Path
from datetime import datetime, timedelta
from google.cloud import storage

@functions_framework.http
def cleanup_strategy_files(request):
    """HTTP Cloud Function to clean up old strategy files.
    
    Args:
        request (flask.Request): The request object
        {
            "retention_days": 7  # optional, number of days of files to keep
        }
    Returns:
        Status of the cleanup operation
    """
    try:
        # Parse request data
        request_json = request.get_json(silent=True) or {}
        retention_days = request.args.get('retention_days', request_json.get('retention_days', 7))
        
        # Calculate cutoff date
        cutoff_date = datetime.now() - timedelta(days=int(retention_days))
        
        # Initialize GCS client
        client = storage.Client()
        
        # Get GCS bucket name from config
        config_path = Path(__file__).resolve().parent.parent.parent / 'config' / 'gcs.json'
        if not config_path.exists():
            return {
                'status': 'error',
                'message': 'GCS configuration not found'
            }, 500
            
        with open(config_path) as f:
            import json
            config = json.load(f)
            bucket_name = config.get('GCS_BUCKET_NAME')
            
        if not bucket_name:
            return {
                'status': 'error',
                'message': 'GCS bucket name not found in configuration'
            }, 500

        # Get bucket
        bucket = client.bucket(bucket_name)
        
        # List and filter strategy files
        blobs = bucket.list_blobs(prefix='strategies/strategy_')
        deleted_files = []
        
        for blob in blobs:
            # Extract date from filename (format: strategy_YYYY-MM-DD.{md,txt})
            try:
                filename = Path(blob.name).name
                date_str = filename.split('_')[1].split('.')[0]
                file_date = datetime.strptime(date_str, '%Y-%m-%d')
                
                if file_date < cutoff_date:
                    blob.delete()
                    deleted_files.append(blob.name)
            except (IndexError, ValueError):
                # Skip files that don't match expected naming pattern
                continue

        return {
            'status': 'success',
            'message': f'Deleted {len(deleted_files)} files older than {retention_days} days',
            'deleted_files': deleted_files
        }

    except Exception as e:
        return {
            'status': 'error',
            'message': str(e)
        }, 500