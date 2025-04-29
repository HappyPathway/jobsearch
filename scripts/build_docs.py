#!/usr/bin/env python
"""Build documentation from code annotations.

This script builds the technical API reference documentation by using
mkdocs and mkdocstrings to extract information from docstrings and
type annotations in the codebase.

Usage:
    python scripts/build_docs.py
"""

import os
import sys
import subprocess
from pathlib import Path

def ensure_dependencies():
    """Ensure all required dependencies are installed."""
    dependencies = [
        "mkdocs",
        "mkdocs-material", 
        "mkdocstrings[python]",
        "pymdown-extensions"
    ]
    
    print("Checking dependencies...")
    try:
        for dep in dependencies:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", dep],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error installing dependencies: {e}")
        return False

def generate_api_docs():
    """Generate or update API reference files.
    
    Note: This function is currently disabled as we're keeping only
    the main documentation files without auto-generated API docs.
    """
    # Documentation is now manually maintained in the docs directory
    print("API documentation generation is currently disabled.")
    pass

def build_docs():
    """Build documentation site using mkdocs."""
    try:
        print("Building documentation site...")
        subprocess.run(
            ["mkdocs", "build"], 
            check=True, 
            cwd=Path(__file__).parent.parent
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error building documentation: {e}")
        return False

def serve_docs():
    """Serve documentation site for preview."""
    try:
        print("Starting documentation server...")
        subprocess.run(
            ["mkdocs", "serve"],
            check=False,
            cwd=Path(__file__).parent.parent
        )
        return True
    except KeyboardInterrupt:
        print("Documentation server stopped.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error serving documentation: {e}")
        return False

def main():
    """Main execution function."""
    if not ensure_dependencies():
        print("Failed to install required dependencies.")
        return 1
        
    generate_api_docs()
    
    if not build_docs():
        print("Failed to build documentation.")
        return 1
    
    print("Documentation built successfully!")
    
    serve_option = input("Would you like to preview the documentation? (y/n): ")
    if serve_option.lower() in ('y', 'yes'):
        serve_docs()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
