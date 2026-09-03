"""DDD - a data dictionary for the global variables of an embedded software project.

The package is organised in layers, each knowing only what is below it:

* :mod:`ddd.models`   - the pydantic contracts describing the json file formats
* :mod:`ddd.loading`  - reads a project/component tree from disk into those contracts
* :mod:`ddd.analysis` - resolves the data objects and runs the consistency checks
* :mod:`ddd.ir`       - the resolved dictionary, the contract the backends consume
* :mod:`ddd.backends` - renders that dictionary: ``backends.c`` and ``backends.a2l``
"""

from ddd.diagnostics import Diagnostic, DiagnosticBag, Severity

__all__ = ["Diagnostic", "DiagnosticBag", "Severity", "__version__"]

__version__ = "0.7.0"
