"""``ddd gui``: a browser interface over one project's description files, on this computer
by default.

A preview. The pages are compiled from ``gui/`` into ``static/`` beside this file; the server
(:mod:`ddd.gui.server`) serves them and the JSON API (:mod:`ddd.gui.api`), which answers from
the open project (:mod:`ddd.gui.session`). Nothing is imported here, so that ``import
ddd.gui.session`` costs only what it uses.
"""
