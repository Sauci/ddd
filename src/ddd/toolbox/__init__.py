"""The toolbox: tools run once, on the way into DDD or out of it, rather than in every build.

``ddd tool`` is their namespace on the command line (section 7.3 of ``SPEC.md``), and each
tool is a module here. :mod:`ddd.toolbox.from_elf` is the first: it describes the C variables
of a linked ELF image as DDD declarations.
"""
