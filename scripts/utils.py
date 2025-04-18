import os
import logging
from contextlib import contextmanager
from sqlalchemy.orm import Session
from pathlib import Path
from models import get_session

# Use the GCS-aware session management
def get_session():
    # Import here to avoid circular import
    from models import get_session as models_get_session
    return models_get_session()

@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations."""
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()

def get_db_path():
    """Get the path to the SQLite database file"""
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), 'career_data.db')