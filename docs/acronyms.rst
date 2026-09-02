Acronyms
========

The vocabulary of this documentation comes from two worlds that rarely overlap in one head:
the embedded software project, which speaks of components, images and linkers, and the
measurement and calibration world, whose file format is a list of upper case keywords with
thirty years of history behind them. The two tables below expand both, and say - where it
makes a difference - what the term means for DDD in particular.

Acronyms and abbreviations
--------------------------

.. list-table::
   :header-rows: 1
   :widths: 14 86

   * - Term
     - Meaning
   * - A2L
     - The file extension, and by extension the common name, of the ASAM MCD-2 MC description
       of an ECU. DDD generates one per project, named ``<Project>.a2l``: it is what a
       measurement and calibration tool reads to know which values exist in the software,
       where they live, how a raw value is converted into a physical one and within which
       limits it may be calibrated.
   * - ASAM
     - Association for Standardisation of Automation and Measuring Systems, the body that
       publishes the MCD-2 MC standard the generated a2l follows.
   * - ASAP2
     - The former name of ASAM MCD-2 MC, still used for the version number of the format.
       ``ASAP2_VERSION 1 61`` in the second line of every generated file says that DDD writes
       version 1.6.1.
   * - CCP
     - CAN Calibration Protocol, the older of the two protocols a calibration tool uses to
       reach the values described by an a2l. DDD describes the data, not the transport: no
       generated file contains an ``IF_DATA`` section for CCP.
   * - CI
     - Continuous integration, the automated build that runs the checks on every change. DDD
       is built for it: every command that produces findings also produces them as json with
       ``--format json``, and the exit code separates a clean run (``0``) from findings
       (``1``) and from a wrong invocation (``2``).
   * - DAQ
     - Data acquisition, the mechanism by which an XCP slave sends measured values
       cyclically, each one subscribed to an *event*. DDD writes which event a measurement
       belongs to when a :doc:`raster <file_formats/rasters>` names one; the module level
       list that configures the events themselves is not part of what DDD writes.
   * - DDD
     - The tool this documentation describes: a data dictionary for the global variables of a
       component based embedded software project. The same three letters name the command,
       the importable python package and the double extension of the description files,
       ``*.ddd.json``; the distribution on the package index is called ``ddd-tool``, because
       ``ddd`` was taken.
   * - DWARF
     - The debugging data format usually embedded in an ELF file, which describes the symbols
       of the compiled software. DDD does not read it: the addresses it needs for the a2l are
       supplied as a json map with ``--address-map``, produced from the linker output by
       whatever already parses it in the build.
   * - ECU
     - Electronic control unit, a piece of electronic hardware running the software whose
       variables DDD describes. The term appears in the a2l keywords - ``ECU_ADDRESS`` - and
       in the calibration vocabulary in general; DDD itself is not tied to any industry and
       says *target* or *image* where it can.
   * - ELF
     - Executable and Linkable Format, the format of the linked software image on most
       toolchains. It is the artefact whose link step decides the addresses that later go
       into the a2l, and the file an a2l address patcher resolves the generated
       ``SYMBOL_LINK`` entries against.
   * - IR
     - Intermediate representation: the resolved data dictionary that sits between the
       checking front end and the output backends, with every limit filled in, every shape
       worked out and the producing component's definition selected. It is a published
       contract rather than an internal detail - ``ddd dump`` writes it out and
       ``ddd schema dictionary`` publishes its json schema, so a generator that DDD does not
       ship can consume it.
   * - json
     - JavaScript Object Notation, the format of every file DDD reads: the project and
       component descriptions, the address map, the archived
       dictionary used as a comparison baseline, and the machine readable diagnostics.
   * - MCD-2 MC
     - Measurement, Calibration and Diagnostics, part 2, Measurement and Calibration: the
       formal ASAM name of the format everybody calls a2l.
   * - XCP
     - Universal Measurement and Calibration Protocol, the successor of CCP. An exported
       measurement with a :doc:`raster <file_formats/rasters>` reaches the generated a2l with
       an ``IF_DATA XCP`` block naming its DAQ event; the rest of the protocol - the event
       configuration, ``PROTOCOL_LAYER`` and transport - is not part of what DDD writes.

a2l keywords
------------

These are the keywords that appear in the files DDD generates, and therefore in the
:doc:`generated artefacts </generated_artefacts>` chapter and in the :doc:`faq </faq>`. They
are listed here in the order in which they build on each other rather than alphabetically, so
that the table can be read as a description of one file.

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Keyword
     - Meaning
   * - ``ASAP2_VERSION``
     - Version of the format the file is written in. DDD writes ``ASAP2_VERSION 1 61`` and
       the version is not selectable.
   * - ``MOD_COMMON``
     - Module wide defaults: the alignment of each datatype and the byte order, which
       ``--byte-order`` selects and which appears as ``MSB_LAST`` for little endian targets
       and ``MSB_FIRST`` for big endian ones.
   * - ``MEASUREMENT``
     - One quantity the calibration tool may only read, because the software writes it. Every
       object of kind ``measurement`` becomes one, scalar or array.
   * - ``CHARACTERISTIC``
     - One quantity the calibration tool may write, because the software never does.
       Parameters, value blocks, curves and maps all become one, distinguished by their type
       field: ``VALUE``, ``VAL_BLK``, ``CURVE`` and ``MAP``.
   * - ``VAL_BLK``
     - The ``CHARACTERISTIC`` type of an array of calibration values - a value block, in the
       vocabulary of the description files.
   * - ``AXIS_PTS``
     - The break points of a shared axis, stored once as a record of their own so that every
       curve and map over the same axis can point at them instead of repeating them.
   * - ``AXIS_DESCR``
     - The description, inside a curve or a map, of one of its axes: which attribute it has,
       which quantity indexes it, how many points it holds and within which limits.
   * - ``COM_AXIS``
     - The ``AXIS_DESCR`` attribute meaning *common axis*: the break points are not stored
       inside this characteristic but in a separate ``AXIS_PTS`` record. It is the only
       attribute DDD emits, because an axis in a DDD description is always a data object in
       its own right.
   * - ``AXIS_PTS_REF``
     - The reference from an ``AXIS_DESCR`` to the ``AXIS_PTS`` holding its break points.
       Because a reference that resolves to nothing makes the whole file invalid, an axis
       pointed at by an exported object is always exported too, whatever its ``export``
       setting says.
   * - ``RECORD_LAYOUT``
     - How the bytes of an object are laid out in memory. DDD emits one per datatype and
       storage category and shares it between all objects that deposit into it, which is why
       the generated names read ``RL_VALUES_UWORD`` and ``RL_AXIS_UBYTE``.
   * - ``ROW_DIR``
     - The index mode inside a ``RECORD_LAYOUT`` saying that a two dimensional object is
       stored row wise. It is what makes the a2l agree with the c declaration ``[y][x]``, in
       which the x index runs fastest.
   * - ``COMPU_METHOD``
     - The rule that converts a raw value into a physical one, together with the unit and the
       display format. DDD emits one per distinct conversion and unit and shares it, so two
       objects scaled the same way in the same unit refer to the same method.
   * - ``RAT_FUNC``
     - The ``COMPU_METHOD`` type used for a linear conversion. Its ``COEFFS a b c d e f``
       describe ``raw = (a*phys^2 + b*phys + c) / (d*phys^2 + e*phys + f)``, so
       ``phys = raw * factor + offset`` is written as ``COEFFS 0 1 -offset 0 0 factor``.
   * - ``TAB_VERB``
     - The ``COMPU_METHOD`` type used for an enumeration: the conversion is a verbal table,
       named through a ``COMPU_TAB_REF``.
   * - ``COMPU_VTAB``
     - That verbal table itself - the list of raw values and the text shown for each of them.
       DDD emits one per enum conversion, filled with the enumerator names, so that a
       calibration tool displays ``STATE_FAULT`` where the software stores ``15``.
   * - ``NO_COMPU_METHOD``
     - The placeholder written instead of a method name for an object that has neither a
       conversion nor a unit, and whose raw value is therefore already the physical one.
   * - ``MATRIX_DIM``
     - The dimensions of an array, fastest index first - the reverse of the c declaration
       order. Version 1.6.1 carries exactly three, so an array of eight elements is written
       ``MATRIX_DIM 8 1 1``.
   * - ``ECU_ADDRESS``
     - The address of an object in the target, as it appears on a ``MEASUREMENT``. A
       ``CHARACTERISTIC`` and an ``AXIS_PTS`` carry the same value as their address field
       instead. It is ``0x00000000`` until an address map supplies the real one.
   * - ``SYMBOL_LINK``
     - The name of the symbol an object corresponds to in the linked software, plus an offset.
       DDD always writes it, so that an address patcher can fill the addresses in after the
       link even when no address map was given.
   * - ``GROUP``
     - A named collection of measurements and characteristics, used to organise the objects
       in the calibration tool. DDD emits one per component, containing exactly the objects
       that component declares and that are present in the file.
