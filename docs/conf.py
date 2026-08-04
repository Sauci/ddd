# Configuration file for the Sphinx documentation builder.
#
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys
from pathlib import Path

# The package is documented from the sources rather than from an installed copy, so that the
# documentation of a working tree always describes that working tree.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ddd import __version__

# -- Project information -----------------------------------------------------

project = "DDD"
copyright = "2026, Killian Daly"
author = "Killian Daly"
release = __version__
version = __version__

# -- General configuration ---------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.graphviz",  # draws the entity relationship figures erdantic emits
    "sphinx.ext.viewcode",
    "sphinxcontrib.autodoc_pydantic",
    "sphinxcontrib.autoprogram",
    "sphinxcontrib.plantuml",
]

exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
nitpicky = False

# _templates/versions.html overrides the empty file of that name the theme ships purely to be
# overridden, and is where the version menu of the published site is drawn.
templates_path = ["_templates"]

# No intersphinx: the documentation has to build in an offline container, and an inventory
# that cannot be fetched turns every build into a warning.

# -- Options for HTML output -------------------------------------------------

html_title = "DDD documentation"
html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_theme_options = {
    "navigation_depth": 3,
}
html_css_files = ["css/custom.css"]
html_js_files = ["js/versions.js"]
# The theme puts the logo on the dark block at the top of the sidebar, so it is the dark
# variant that goes there; custom.css repaints that block in the ink the mark is drawn for.
# Both paths are relative to this file, and sphinx copies what they name into _static.
html_logo = "../assets/logo/ddd-logo-dark.svg"
html_favicon = "../assets/logo/ddd-favicon.svg"

# -- Options for LaTeX output ------------------------------------------------

latex_documents = [
    ("index", "ddd.tex", "DDD documentation", author, "manual"),
]
latex_elements = {
    "papersize": "a4paper",
    "preamble": r"\setcounter{tocdepth}{2}",
}

# -- Extension options -------------------------------------------------------

autosummary_generate = True
# Only the class docstring. With "both", every pydantic model would also carry the inherited
# ``BaseModel.__init__`` docstring - three paragraphs of "create a new model by parsing and
# validating input data", repeated under all twenty-six models, one of them containing a
# markdown link that reStructuredText renders verbatim.
autoclass_content = "class"
add_module_names = False
autodoc_member_order = "bysource"
autodoc_typehints = "description"

# The file formats are pydantic models, so the reference pages are generated from the
# contract itself: a field that changes cannot leave its documentation behind.
autodoc_pydantic_model_show_json = True

autodoc_pydantic_model_erdantic_figure = True
autodoc_pydantic_model_erdantic_figure_collapsed = False
autodoc_pydantic_model_show_config_summary = False
autodoc_pydantic_model_show_validator_summary = False
autodoc_pydantic_model_show_validator_members = False
autodoc_pydantic_model_show_field_summary = True
autodoc_pydantic_field_list_validators = False
autodoc_pydantic_field_show_constraints = True
autodoc_pydantic_model_member_order = "bysource"

# plantuml is called through the jar the documentation image ships at /plantuml.jar. A local
# build rarely has that jar at that path, so PLANTUML_JAR points at another copy and JAVA at
# another interpreter; without either, the plain ``plantuml`` launcher on the PATH is used.
_jar = Path(os.environ.get("PLANTUML_JAR", "/plantuml.jar"))
_java = os.environ.get("JAVA", "java")
plantuml = f'"{_java}" -jar "{_jar}"' if _jar.is_file() else "plantuml"
plantuml_output_format = "svg_img"
