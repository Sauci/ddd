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


def _prose() -> str:
    """The page as one line, every run of whitespace a single space, so a sentence is matched
    whatever width it is wrapped to."""
    return " ".join(PAGE.read_text(encoding="utf-8").split())


def test_the_page_likens_running_a_project_to_make() -> None:
    assert (
        "``ddd gui`` runs the code a project names, as ``make`` runs the recipes a Makefile names"
        in _prose()
    )


def test_the_page_says_what_holding_the_token_lets_one_do() -> None:
    assert "It is code execution as the reader" in _prose()


def test_the_page_says_an_edit_cannot_change_which_plugins_run() -> None:
    assert "an edit that would change which plugins the project runs is refused" in _prose()


def test_the_page_leaves_a_process_of_the_reader_s_own_account_undefended() -> None:
    assert (
        "A process already running as this same user is outside what this page defends" in _prose()
    )


def test_the_page_says_the_launch_race_winner_runs_the_project_code() -> None:
    assert "holds the token, and so runs the project's code as the reader" in _prose()


def test_the_page_says_every_reading_of_a_build_record_s_project_meets_a_request_s_rule() -> None:
    assert (
        "Its build records are read as well, for the projects the start page offers and for how "
        "a project is generated: a record's ``project`` is read only under the rule a request's "
        "path meets, and only as a file named ``*.ddd.json``, and a record naming anything else "
        "is read as no record" in _prose()
    )


def test_the_page_says_localhost_is_ddd_gui_whichever_address_a_browser_tries() -> None:
    assert (
        "When it listens on loopback, as it does by default, ``ddd gui`` listens on ``[::1]`` "
        "too, on the very same port, and answers there as it answers on ``127.0.0.1``: "
        "``localhost`` is ``ddd gui`` itself, whichever of the two a browser tries, signed out "
        "until the address it printed is opened there." in _prose()
    )


def test_the_page_says_no_other_program_can_listen_on_ipv6_loopback_at_the_port() -> None:
    assert (
        "No other program can listen on ``[::1]`` at that port: on Windows, ``ddd gui`` binds "
        "both addresses exclusively (``SO_EXCLUSIVEADDRUSE``)." in _prose()
    )


def test_the_page_says_a_fixed_port_listened_on_at_ipv6_loopback_is_refused_naming_it() -> None:
    assert (
        "A fixed ``--port`` another program already listens on at ``[::1]`` is refused before "
        "``ddd gui`` starts, naming the port; left to the system, ``--port 0`` tries another "
        "port instead." in _prose()
    )


def test_the_page_says_none_of_it_is_tested_on_macos() -> None:
    assert "None of this is tested on macOS." in _prose()
