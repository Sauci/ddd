"""DDD - a data dictionary for the global variables of an embedded software project.

The package is organised in four layers:

* :mod:`ddd.models`      - the pydantic contracts describing the json file formats
* :mod:`ddd.loading`     - reads a project/component tree from disk into those contracts
* :mod:`ddd.analysis`    - resolves the variables and runs the consistency checks
* :mod:`ddd.generation`  - renders the c sources and the a2l file with jinja2
"""

from ddd.diagnostics import Diagnostic, DiagnosticBag, Severity

__all__ = ["Diagnostic", "DiagnosticBag", "Severity", "__version__"]

__version__ = "0.1.0"
