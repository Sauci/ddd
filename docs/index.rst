DDD documentation
=================

DDD manages the **global variables** of a component based embedded software project. Every
component declares the variables it produces and consumes in a small json file; DDD checks
that all components agree, generates the c code that allocates the data, and generates the
ASAP2 (a2l) description that measurement and calibration tools read.

.. toctree::
   :maxdepth: 2
   :caption: Using DDD

   getting_started
   concept
   file_formats/index
   consistency_checks
   naming_conventions
   comparing_deliveries
   generated_artefacts
   command_line_interface
   build_integration

.. toctree::
   :maxdepth: 2
   :caption: Reference

   data_contracts
   data_dictionary
   developer_documentation
   faq
   acronyms

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
