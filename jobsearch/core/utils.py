"""Core utility functions."""
from contextlib import contextmanager
from sqlalchemy.orm import Session
from jobsearch.core.database import get_engine

@contextmanager
def session_scope() -> Session:
    """Provide a transactional scope around a series of operations."""
    session = Session(get_engine())
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
