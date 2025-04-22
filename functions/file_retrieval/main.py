import os
import functions_framework
from google.cloud import storage
import tempfile
from pathlib import Path
import mimetypes
from flask import jsonify, make_response

def get_file_type(path):
    """Determine file type from extension"""
    mime_type, _ = mimetypes.guess_type(path)
    if mime_type:
        return mime_type
    return 'application/octet-stream'

@functions_framework.http
def retrieve_file(request):
    """HTTP Cloud Function to retrieve files from GCS.
    
    Args:
        request (flask.Request): The request object
        {
            "file_path": "path/to/file.ext",  # required
            "as_download": false  # optional, forces file download instead of inline display
        }
    Returns:
        The file content with appropriate headers
    """
    try:
        # Get GCS bucket name from environment variable
        bucket_name = os.environ.get('GCS_BUCKET_NAME')
        if not bucket_name:
            return 'GCS_BUCKET_NAME not configured', 500

        # Parse request data
        request_json = request.get_json(silent=True) or {}
        file_path = request_json.get('file_path')
        as_download = request_json.get('as_download', False)
        
        if not file_path:
            return jsonify({'error': 'file_path is required'}), 400

        # Initialize GCS client
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(file_path)

        if not blob.exists():
            return jsonify({'error': f'File not found: {file_path}'}), 404

        # Create a temporary file to download the content
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            blob.download_to_filename(temp_file.name)
            temp_path = Path(temp_file.name)

            # Read the file content
            content = temp_path.read_bytes()
            
            # Clean up temp file
            temp_path.unlink()

            # Determine content type
            content_type = get_file_type(file_path)
            
            # Create response with appropriate headers
            response = make_response(content)
            response.headers['Content-Type'] = content_type
            
            # Set content disposition based on request
            filename = Path(file_path).name
            if as_download or content_type not in ['text/markdown', 'text/plain']:
                response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
            else:
                response.headers['Content-Disposition'] = f'inline; filename="{filename}"'

            return response

    except Exception as e:
        return jsonify({'error': str(e)}), 500