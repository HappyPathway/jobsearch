"""
This module is deprecated. Use jobsearch.core.storage.GCSManager instead.
See core.storage documentation for proper usage.
"""
from jobsearch.core.storage import GCSManager as CoreGCSManager

# Maintain backwards compatibility while migrating
GCSManager = CoreGCSManager

# For backwards compatibility
gcs = GCSManager()

# Add deprecation warnings
import warnings

warnings.warn(
    "jobsearch.features.common.storage is deprecated. "
    "Use jobsearch.core.storage.GCSManager instead. "
    "This module will be removed in a future version.",
    DeprecationWarning,
    stacklevel=2
)