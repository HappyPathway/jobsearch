import os
import logging
from contextlib import contextmanager
from sqlalchemy.orm import Session
from pathlib import Path
from jobsearch.core.models import SessionFactory
from jobsearch.core.storage import gcs

logger = logging.getLogger(__name__)

@contextmanager
def session_scope():
    """DEPRECATED: Use jobsearch.core.database.get_session instead.
    
    This function will be removed in a future version. The core get_session
    function provides proper GCS sync and locking functionality.
    """
    import warnings
    warnings.warn(
        "session_scope() is deprecated. Use jobsearch.core.database.get_session instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
    if not gcs.acquire_lock():
        logger.error("Could not acquire database lock after retries. Exiting gracefully.")
        raise Exception("Database is currently locked by another process. Please try again later.")

    session = SessionFactory()
    try:
        yield session
        session.commit()
        # Upload the database after successful commit
        gcs.upload_db()
    except Exception as e:
        session.rollback()
        raise
    finally:
        if session:
            session.close()
        gcs.release_lock()

def get_db_path():
    """Get the path to the SQLite database file"""
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), 'career_data.db')