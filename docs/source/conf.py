"""Sphinx configuration for jobsearch documentation."""

import os
import sys

# Add jobsearch package to path
sys.path.insert(0, os.path.abspath('../..'))

# Project information
project = 'JobSearch'
copyright = '2025, Career Automation'
author = 'Career Automation Team'
release = '1.0.0'

# General configuration
extensions = [
    'sphinx.ext.autodoc',    # Core extension for API docs
    'sphinx.ext.viewcode',   # Add links to view source code
    'sphinx.ext.napoleon',   # Support for Google style docstrings
    'autoapi.extension',     # Auto-generate API documentation
    'myst_parser',           # Support for Markdown files
]

# AutoAPI settings
autoapi_type = 'python'
autoapi_dirs = ['../../jobsearch']
autoapi_options = [
    'members',
    'undoc-members',
    'private-members',
    'show-inheritance',
    'show-module-summary',
    'special-members',
]

# Set the default domain and language
primary_domain = 'py'
language = 'en'

# Napoleon settings for Google-style docstrings
napoleon_google_docstring = True  # Enable Google-style docstrings
napoleon_numpy_docstring = False  # Disable NumPy-style docstrings
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = True
napoleon_use_admonition_for_examples = True
napoleon_use_admonition_for_notes = True
napoleon_use_admonition_for_references = True

# Add any paths that contain templates here
templates_path = ['_templates']

# Enable MyST for Markdown parsing (to work with existing MD docs)
source_suffix = {
    '.rst': 'restructuredtext',
    '.md': 'markdown',
}

# The master toctree document
master_doc = 'index'

# List of patterns to exclude from source
exclude_patterns = []

# Theme configuration
html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']

# Include module names in function/class documentation
add_module_names = True

# If true, `todo` and `todoList` produce output
todo_include_todos = True
