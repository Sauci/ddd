"""The security page's table of routes, held against the server's own route table."""

from pathlib import Path

from ddd.gui.api import ROUTES

PAGE = Path(__file__).parents[1] / "docs" / "gui_security.rst"


def _rows() -> list[tuple[str, ...]]:
    """The list-table's rows under ``.. _gui-security-routes:``, each cell stripped of its
    literal markup. An empty cell's line is ``     - `` with a trailing space; a line an
    editor trimmed to ``     -`` still counts as one, since nothing under ``docs/`` otherwise
    carries trailing whitespace to protect. The header row is checked, not merely dropped: a
    swapped or renamed column would otherwise pass unseen, every data row still lining up."""
    lines = PAGE.read_text(encoding="utf-8").split(".. _gui-security-routes:", 1)[1].splitlines()
    rows: list[list[str]] = []
    for line in lines:
        if line.startswith("   * - "):
            rows.append([line[7:].strip().strip("`")])
        elif rows and (line.startswith("     - ") or line.rstrip() == "     -"):
            rows[-1].append(line[7:].strip().strip("`"))
        elif rows and line and not line.startswith(" "):
            break
    assert rows[0] == ["Method", "Path", "Writes", "Opens a project", "Runs plugins", "Waits"]
    return [tuple(row) for row in rows[1:]]  # the header row checked above, then left out


def _yes(flag: bool) -> str:
    return "yes" if flag else ""


def test_the_page_names_every_route_with_its_policy() -> None:
    expected = [
        (
            route.method,
            route.path,
            _yes(route.policy.writes),
            _yes(route.policy.opens),
            _yes(route.policy.runs_plugins),
            _yes(route.policy.waits),
        )
        for route in ROUTES
    ]
    assert _rows() == expected
