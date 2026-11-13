"""Sphinx configuration for the H3V public Python API."""
from importlib.metadata import version as _package_version
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

project = "H3V"
author = "H3V contributors"
release = _package_version("h3v")
version = release
extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.doctest",
    "sphinx.ext.githubpages",
]
source_suffix = {".rst": "restructuredtext", ".md": "markdown"}
root_doc = "index"
myst_heading_anchors = 3
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "contributing.md", "documentation_guidelines.md"]
autosummary_generate = False
autodoc_typehints = "description"
napoleon_numpy_docstring = True
napoleon_preprocess_types = True
napoleon_google_docstring = False
nitpicky = True
html_theme = "sphinx_book_theme"
html_title = "H3V documentation"
html_theme_options = {
    "repository_url": "https://github.com/piglabsai/h3v",
    "use_repository_button": True,
    "show_navbar_depth": 2,
}
html_show_sourcelink = False
doctest_global_setup = "import h3v\nfrom h3.api import basic_int as h3"
