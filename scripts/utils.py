import os
import logging
from contextlib import contextmanager
from sqlalchemy.orm import Session
from pathlib import Path
from models import SessionFactory

@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations."""
    session = SessionFactory()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        raise
    finally:
        if session:
            session.close()

def get_db_path():
    """Get the path to the SQLite database file"""
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), 'career_data.db')