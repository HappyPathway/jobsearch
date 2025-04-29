"""Core utility functions."""

# DEPRECATED: Database session management functions have been moved
# All code should use jobsearch.core.database.get_session() which provides:
# - Database locking
# - GCS sync
# - Proper monitoring
# - Error tracking
# - Auto-commit and rollback
# 
# Example usage:
#   from jobsearch.core.database import get_session
#   
#   with get_session() as session:
#       results = session.query(MyModel).all()
#       session.add(new_object)
#       # Commits automatically on success
#       # Rolls back on error
#       # Handles GCS sync
