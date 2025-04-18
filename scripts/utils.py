import os
from pathlib import Path
from logging_utils import setup_logging

# Use the GCS-aware session management
def get_session():
    # Import here to avoid circular import
    from models import get_session as models_get_session
    return models_get_session()

def get_db_path():
    """Get the path to the SQLite database file"""
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), 'career_data.db')