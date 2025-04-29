#!/usr/bin/env python3
"""Generate Sphinx documentation for the JobSearch project.

This script sets up and builds Sphinx documentation for the JobSearch project.
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    """Set up and build Sphinx documentation."""
    # Get base paths
    base_dir = Path(__file__).parent.parent
    docs_dir = base_dir / "docs"
    
    # Install dependencies
    print("Installing Sphinx dependencies...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", 
         "sphinx", "sphinx-rtd-theme", "sphinx-autoapi", "myst-parser"],
        check=True
    )
    
    # Build documentation
    print(f"Building documentation in {docs_dir}...")
    result = subprocess.run(
        ["sphinx-build", "-b", "html", ".", "_build/html"],
        cwd=docs_dir,
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"Error building documentation:\n{result.stderr}")
        return 1
    
    print(f"Documentation built successfully in {docs_dir}/_build/html")
    print(f"View it by opening {docs_dir}/_build/html/index.html")
    return 0

if __name__ == "__main__":
    sys.exit(main())
