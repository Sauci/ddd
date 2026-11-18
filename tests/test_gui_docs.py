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


def test_the_page_says_opening_a_project_here_is_running_it() -> None:
    assert "Opening a project here is running it." in _prose()


def test_the_page_says_what_holding_the_token_lets_one_do() -> None:
    assert (
        "It is code execution as the reader: whoever holds it acts on the project's descriptions "
        "as the reader does, and ``ddd gui`` runs the plugins they name, as ``ddd check`` does."
        in _prose()
    )


def test_the_page_says_an_edit_cannot_change_which_plugins_the_descriptions_name() -> None:
    assert (
        "The token names no new code: an edit that would change which plugins the project's "
        "descriptions name is refused, ``409``, so the reader makes that change in a text "
        "editor, not through the page." in _prose()
    )


def test_the_page_says_what_the_token_can_run() -> None:
    assert (
        "What it can run is what descriptions already name: the open project's, and those of a "
        "project the start page offers or a baseline under the directory ``ddd gui`` was "
        "started in, which the page may open or compare against." in _prose()
    )


def test_the_page_says_a_description_that_does_not_load_runs_none_of_its_plugins() -> None:
    assert (
        "A description that does not load runs none of the plugins it names, whichever way an "
        "edit leaves it." in _prose()
    )


def test_the_page_leaves_a_process_of_the_reader_s_own_account_undefended() -> None:
    assert (
        "A process already running as this same user is outside what this page defends: it "
        "reads these files and runs this code with no token at all." in _prose()
    )


def test_the_page_says_the_launch_race_winner_runs_the_project_code() -> None:
    assert "holds the token, and so runs the project's code as the reader" in _prose()


def test_the_page_says_the_launch_race_winner_holds_what_any_holder_of_the_token_holds() -> None:
    assert (
        "What the winner holds is what any holder of the token holds, as *Whoever holds the "
        "token*, under *What it trusts*, says: it acts on the project's descriptions as the "
        "reader, and runs no code but what descriptions already name." in _prose()
    )


def test_the_page_says_the_launch_race_winner_may_be_any_local_user_s_program() -> None:
    assert (
        "The winner may be any local user's program, not only one of the reader's own account: "
        "on a shared machine, another user's program that wins holds the reader's power over "
        "the project for the rest of the run, which a program of another user did not hold "
        "before. A process already running as this same user is outside what this page "
        "defends, as *Whoever holds the token* says; the race is where any other local user's "
        "program reaches the same ground." in _prose()
    )


def test_the_page_says_the_opener_s_command_line_is_readable_on_linux_and_macos_alike() -> None:
    assert (
        "launcher's command line, which any local user can read on Linux and on macOS alike, "
        "and presenting that code" in _prose()
    )


def test_the_page_says_either_cause_leaves_the_browser_signed_out_and_the_advice_the_same() -> None:
    assert (
        "Either way, the browser ``ddd gui`` opened says it is signed out, and the advice is the "
        "same: restart ``ddd gui``." in _prose()
    )


def test_the_page_says_what_the_line_on_the_terminal_tells_the_reader_to_do() -> None:
    assert (
        "The line says that nothing more is needed only if the browser ``ddd gui`` opened "
        "landed on the project, and that if it says it is signed out, the reader stops "
        "``ddd gui`` and starts it again, which mints a new code and a new token, and opens the "
        "address printed then: a restart takes the token from the winner, and this run's "
        "address, opened since, does not." in _prose()
    )


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


def test_the_page_says_a_navigation_a_redirect_continues_is_one_the_browser_began() -> None:
    assert (
        "the gate lets through by design a navigation marked ``Sec-Fetch-Site: none``, which a "
        "browser sends for a navigation it begins itself - an address typed, or chosen from a "
        "bookmark - and for one a redirect continues from such a beginning, whatever site the "
        "address typed or chosen was; an older browser marks such a navigation with nothing."
        in _prose()
    )


def test_the_page_says_such_a_navigation_lands_signed_in_on_its_last_address() -> None:
    assert "Either way it lands, signed in, on the page its last address names, just as above." in (
        _prose()
    )


def test_the_page_says_a_cookie_rode_the_two_navigations_a_browser_begins_itself() -> None:
    assert (
        "The two a browser begins itself landed so when the token was a cookie as well: a "
        "``SameSite=Strict`` cookie rode them." in _prose()
    )


def test_the_page_says_to_open_ddd_gui_from_its_own_address_alone() -> None:
    assert (
        "Open ``ddd gui``'s pages from the address it prints, or from the page itself, rather "
        "than from a link someone else wrote, or an address that sends the browser on to it."
        in _prose()
    )


def test_the_page_says_a_wait_for_the_state_gives_its_slot_back_once_the_page_has_gone() -> None:
    assert (
        "A wait for the state to change, which the page keeps open, looks every second whether "
        "the page is still there, and gives its slot back once it is not - reloaded, or its tab "
        "closed." in _prose()
    )
