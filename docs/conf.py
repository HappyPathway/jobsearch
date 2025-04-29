# Configuration file for the Sphinx documentation builder.

# -- Project information -----------------------------------------------------
project = 'JobSearch Automation Platform'
copyright = '2025, JobSearch Team'
author = 'JobSearch Team'
release = '1.0.0'

# -- General configuration ---------------------------------------------------
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.viewcode',
    'sphinx.ext.napoleon',
    'autoapi.extension',
    'myst_parser',
]

# AutoAPI settings
autoapi_type = 'python'
autoapi_dirs = ['../jobsearch']
autoapi_output = 'api'
autoapi_add_toctree_entry = True
autoapi_keep_files = True  # Keep generated files for inspection
autoapi_python_class_content = 'both'  # Include both class docstring and init docstring
autoapi_options = [
    'members', 
    'undoc-members',
    'private-members',
    'show-inheritance',
    'show-module-summary',
    'special-members',
]

# Add support for Markdown files
source_suffix = {
    '.rst': 'restructuredtext',
    '.md': 'markdown',
}

templates_path = ['_templates']
exclude_patterns = []

# -- Options for HTML output -------------------------------------------------
html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
