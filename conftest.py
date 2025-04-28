"""Root conftest.py to configure test environment."""
import os
import sys
from pathlib import Path

# Add the root directory to Python path for proper imports
root_dir = Path(__file__).parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
