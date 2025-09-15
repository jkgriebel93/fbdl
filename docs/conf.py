# Configuration file for the Sphinx documentation builder.
#
# Minimal, repo-local configuration to build docs for the fbdl project.

import os
import sys
from datetime import datetime
from pathlib import Path

# Add the project src directory to sys.path so autodoc can import fbdl
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# -- Project information -----------------------------------------------------

project = "fbdl"
# Keep version in sync with pyproject.toml
release = "0.0.1"
copyright = f"{datetime.now().year}, fbdl"

autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "undoc-members": True,
    "show-inheritance": True,
}

autosummary_generate = True

# Mock heavy/optional third-party packages so docs can build without them
autodoc_mock_imports = [
    "yt_dlp",
    "mutagen",
    "requests",
    "ffmpeg",
]

# -- General configuration ---------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx_click",
]

napoleon_google_docstring = True
napoleon_numpy_docstring = False

templates_path = ["_templates"]
exclude_patterns = [
    "_build",
    "Thumbs.db",
    ".DS_Store",
]

# -- Options for HTML output -------------------------------------------------

html_theme = "alabaster"
html_static_path = ["_static"]
