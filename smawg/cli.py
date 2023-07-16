#!/usr/bin/env python3

"""CLI client for Small World engine.

This module can serve as an example of how to use `smawg` library.

Running this module directly is deprecated, run it using `smawg play`.

See https://github.com/expurple/smawg for more info about the project.
"""


import json
import sys
from argparse import ArgumentParser, Namespace, RawDescriptionHelpFormatter
from importlib import import_module
from pathlib import Path
from typing import Iterable, Literal, Type, assert_never

from pydantic import TypeAdapter
from tabulate import tabulate

from smawg import AbstractRules, Assets, Game, RulesViolation
from smawg._metadata import PACKAGE_DIR, VERSION


__all__ = ["argument_parser", "root_command"]


_TITLE = f"smawg CLI v{VERSION}"
_HELP_SUGGESTION = "Type 'help' to see available commands."
_VISIT_HOME_PAGE = "For more info, visit https://github.com/expurple/smawg"
_START_SCREEN = "\n".join([_TITLE, _HELP_SUGGESTION, _VISIT_HOME_PAGE, ""])
_HELP = """\
Available commands:
    help                       show this message
    quit                       quit game

    show-combos                show available combos
    show-players               show general player stats
    show-regions <player>      show regions owned by <player>

    [?] combo <index>          pick race+ability combo by <index>
    [?] abandon <region>       abandon <region> by index
    [?] conquer <region>       conquer <region> by index
    [?] conquer-dice <region>  conquer <region>, using the reinforcements dice
    [?] deploy <n> <region>    deploy <n> tokens from hand to <region>
    [?] redeploy               pick up tokens, leaving 1 in each region
    [?] decline                enter decline
    [?] end-turn               end turn and give control to the next player

Put '?' before any command from the last group to "dry run" it.
For example, this command will tell if you're allowed to conquer region 3,
but won't actually attempt to conquer it:

    ? conquer 3

Press Tab to use command autocompletion."""

_COMMANDS = [
    "help", "quit", "show-combos", "show-players", "show-regions", "combo",
    "abandon", "conquer", "conquer-dice", "deploy", "redeploy", "decline",
    "end-turn"
]


_Command = (
    Literal["help", "quit", "show-combos", "show-players"]
    | tuple[Literal["show-regions"], int]
    | tuple[bool, Literal["combo", "abandon", "conquer", "conquer-dice"], int]
    | tuple[bool, Literal["deploy"], int, int]
    | tuple[bool, Literal["redeploy", "decline", "end-turn"]]
)


def _parse_command(line: str) -> _Command | None:
    """Parse a CLI `Command` from string.

    Return `None` if the line is empty.

    Raise:
    * `smawg.cli._InvalidCommand`
        if command is unknown, given wrong number or arguments,
        or a dry run is requested for command that doesn't support it.
    * `ValueError`
        if some argument has invalid type or value.
    """
    line = line.strip()
    dry_run = line.startswith("?")
    if dry_run:
        line = line.removeprefix("?").strip()
    if line == "":
        return None
    command, *args = line.split()
    dry_run_err = _InvalidCommand(f"'{command}' does not support dry run mode")
    match command:
        case "help" | "quit" | "show-combos" | "show-players":
            if dry_run:
                raise dry_run_err
            _parse_ints(args, n=0)
            return command
        case "show-regions":
            if dry_run:
                raise dry_run_err
            [player] = _parse_ints(args, n=1)
            return ("show-regions", player)
        case "combo" | "abandon" | "conquer" | "conquer-dice":
            [arg] = _parse_ints(args, n=1)
            return (dry_run, command, arg)
        case "deploy":
            [n, region] = _parse_ints(args, n=2)
            return (dry_run, "deploy", n, region)
        case "redeploy" | "decline" | "end-turn":
            _parse_ints(args, n=0)
            return (dry_run, command)
        case _:
            raise _InvalidCommand(f"unknown command '{command}'")


def _parse_ints(args: list[str], *, n: int) -> list[int]:
    """Parse `args` as a list of `n` integers."""
    if len(args) != n:
        raise _InvalidCommand(f"expected {n} argument(s), but got {len(args)}")
    return [_parse_int(a) for a in args]


def _parse_int(s: str) -> int:
    """Parse an integer or raise `ValueError` with a frendly message."""
    try:
        return int(s)
    except ValueError:
        raise ValueError(f"'{s}' is not an integer")


def _autocomplete(text: str, state: int) -> str | None:
    """Command completer for `readline`."""
    results: list[str | None] = [c for c in _COMMANDS if c.startswith(text)]
    results.append(None)
    return results[state]


def argument_parser() -> ArgumentParser:
    """Configure and create a command line argument parser."""
    parser = ArgumentParser(
        description=f"CLI client for playing smawg {VERSION}",
        epilog=_VISIT_HOME_PAGE
    )
    parser.add_argument(
        "assets_file",
        metavar="ASSETS_FILE",
        help="path to JSON file with assets"
    )
    parser.add_argument(
        "--rules",
        metavar="RULES_PLUGIN",
        default=f"{PACKAGE_DIR}/default_rules.py",
        help="import RULES_PLUGIN instead of smawg/default_rules.py"
    )
    parser.add_argument(
        "-s", "--no-shuffle",
        action="store_true",
        help="don't shuffle data from ASSETS_FILE"
    )
    parser.add_argument(
        "-d", "--read-dice",
        action="store_true",
        help="read dice roll results from stdin instead of generating randomly"
    )
    parser.add_argument(
        "-r", "--relative-path",
        action="store_true",
        help="search for ASSETS_FILE inside of smawg package directory"
    )
    return parser


def _read_dice() -> int:
    """Get result of a dice roll from an interactive console."""
    prompt = "Enter the result of the dice roll: "
    while True:
        try:
            return int(input(prompt))
        except ValueError:
            prompt = "The result must be an integer, try again: "


def _import_rules(filename: str) -> Type[AbstractRules]:
    """Dynamically load `Rules` from a Python file."""
    rules_file_path = Path(filename).resolve()
    rules_file_name = rules_file_path.name
    rules_dir_name = str(rules_file_path.parent)
    sys.path.append(rules_dir_name)
    rules_module = import_module(rules_file_name[:-3])
    rules: Type[AbstractRules] = rules_module.Rules
    return rules


class _InvalidCommand(ValueError):
    """Exception raised in `_Client` when an invalid command is entered."""

    pass


class _Client:
    """Handles console IO."""

    def __init__(self, args: Namespace) -> None:
        """Construct `_Client` with respect to command line `args`."""
        assets_file = args.assets_file
        if args.relative_path:
            assets_file = f"{PACKAGE_DIR}/{assets_file}"
        with open(assets_file) as file:
            assets_json = json.load(file)
        assets: Assets = TypeAdapter(Assets).validate_python(assets_json)
        if not args.no_shuffle:
            assets = assets.shuffle()
        rules = _import_rules(args.rules)
        if args.read_dice:
            game = Game(assets, rules, dice_roll_func=_read_dice)
        else:
            game = Game(assets, rules)
        self.game = game
        self.player_of_last_command = -1  # Not equal to any actual player.
        self.reported_game_end = False

    def run(self) -> None:
        """Interpret user commands until stopped by `'quit'`, ^C or ^D."""
        print(_START_SCREEN)
        try:
            self._run_main_loop()
        except (EOFError, KeyboardInterrupt):
            exit(1)

    def _run_main_loop(self) -> None:
        while True:
            self._print_change_player_message()
            line = input("> ")
            try:
                command = _parse_command(line)
                if command is not None:
                    self._execute(command)
            except _InvalidCommand as e:
                print(f"Invalid command: {e.args[0]}")
                print(_HELP_SUGGESTION)
            except ValueError as e:
                print(f"Invalid argument: {e.args[0]}")
            except RulesViolation as e:
                print(f"Rules violated: {e.args[0]}")

    def _print_change_player_message(self) -> None:
        """If active player changed or game ended, print a message."""
        if self.game.has_ended and not self.reported_game_end:
            self._command_show_players()
            print("")
            print(f"{self.game.n_turns} turns have passed, the game is over.")
            print("You can take a final look around and type 'quit' to quit.")
            self.reported_game_end = True
            self.player_of_last_command = self.game.player_id
        elif self.game.player_id != self.player_of_last_command:
            if self.game.is_in_redeployment_turn:
                print(f"Player {self.game.player_id} redeploys "
                      f"{self.game.player.tokens_on_hand} tokens.")
            else:
                print(f"Player {self.game.player_id} starts turn "
                      f"{self.game.current_turn}/{self.game.n_turns}.")
            self.player_of_last_command = self.game.player_id

    def _execute(self, command: _Command) -> None:
        """Execute the given `command`.

        Raise:
        * `ValueError`
            if some argument has invalid value.
        * `smawg.RulesViolation` subtypes
            if given command violates the game rules.
        """
        match command:
            case "help":
                print(_HELP)
            case "quit":
                exit(0)
            case "show-combos":
                self._command_show_combos()
            case "show-players":
                self._command_show_players()
            case ("show-regions", int(player_id)):
                self._command_show_regions(player_id)
            case (bool(dry_run), "combo", int(index)):
                self._command_combo(index, dry_run=dry_run)
            case (bool(dry_run), "abandon", int(region)):
                self._command_abandon(region, dry_run=dry_run)
            case (bool(dry_run), "conquer", int(region)):
                self._command_conquer(region, dry_run=dry_run)
            case (bool(dry_run), "conquer-dice", int(region)):
                self._command_conquer_dice(region, dry_run=dry_run)
            case (bool(dry_run), "deploy", int(n), int(region)):
                self._command_deploy(n, region, dry_run=dry_run)
            case (bool(dry_run), "redeploy"):
                self._command_redeploy(dry_run=dry_run)
            case (bool(dry_run), "decline"):
                self._command_decline(dry_run=dry_run)
            case (bool(dry_run), "end-turn"):
                self._command_end_turn(dry_run=dry_run)
            case not_covered:
                # As of 1.4.1, mypy can't deduce `not_covered: Never` here.
                # Remove 'type:ignore' when this is fixed in mypy.
                assert_never(not_covered)  # type:ignore

    def _command_show_players(self) -> None:
        headers = ["Player", "Active ability", "Active race", "Declined race",
                   "Tokens on hand", "Coins"]
        rows = []
        for i, p in enumerate(self.game.players):
            rows.append([
                i,
                p.active_ability.name if p.active_ability else "-",
                p.active_race.name if p.active_race else "-",
                p.decline_race.name if p.decline_race else "-",
                p.tokens_on_hand,
                p.coins
            ])
        print(tabulate(rows, headers, stralign="center", numalign="center"))

    def _command_show_combos(self) -> None:
        headers = ["Price", "Coins you get", "Ability", "Race",
                   "Tokens you get"]
        rows = [(i, c.coins, c.ability.name, c.race.name, c.base_n_tokens)
                for i, c in enumerate(self.game.combos)]
        print(tabulate(rows, headers, stralign="center", numalign="center"))

    def _command_show_regions(self, player_id: int) -> None:
        if not 0 <= player_id < len(self.game.players):
            msg = f"<player> must be between 0 and {len(self.game.players)}"
            raise ValueError(msg)
        player = self.game.players[player_id]
        headers = ["Region", "Tokens", "Type"]
        rows = []
        for r, t in player.active_regions.items():
            rows.append([r, t, "Active"])
        for r in player.decline_regions:
            rows.append([r, 1, "Declined"])
        print(tabulate(rows, headers, stralign="center", numalign="center"))

    def _command_combo(self, i: int, *, dry_run: bool) -> None:
        if dry_run:
            errors = self.game.rules.check_select_combo(i)
            self._raise_first_or_print_ok(errors)
        else:
            self.game.select_combo(i)

    def _command_abandon(self, region: int, *, dry_run: bool) -> None:
        if dry_run:
            errors = self.game.rules.check_abandon(region)
            self._raise_first_or_print_ok(errors)
        else:
            self.game.abandon(region)

    def _command_conquer(self, region: int, *, dry_run: bool) -> None:
        if dry_run:
            errors = self.game.rules.check_conquer(region, use_dice=False)
            self._raise_first_or_print_ok(errors)
        else:
            self.game.conquer(region)

    def _command_conquer_dice(self, region: int, *, dry_run: bool) -> None:
        if dry_run:
            errors = self.game.rules.check_conquer(region, use_dice=True)
            self._raise_first_or_print_ok(errors)
        else:
            dice_value = self.game.conquer(region, use_dice=True)
            is_success = region in self.game.player.active_regions
            description = "successful" if is_success else "unsuccessful"
            print(f"Rolled {dice_value} on the dice, "
                  f"conquest was {description}.")

    def _command_deploy(self, n: int, region: int, *, dry_run: bool) -> None:
        if dry_run:
            errors = self.game.rules.check_deploy(n, region)
            self._raise_first_or_print_ok(errors)
        else:
            self.game.deploy(n, region)

    def _command_redeploy(self, *, dry_run: bool) -> None:
        if dry_run:
            errors = self.game.rules.check_start_redeployment()
            self._raise_first_or_print_ok(errors)
        else:
            self.game.start_redeployment()

    def _command_decline(self, *, dry_run: bool) -> None:
        if dry_run:
            errors = self.game.rules.check_decline()
            self._raise_first_or_print_ok(errors)
        else:
            self.game.decline()

    def _command_end_turn(self, *, dry_run: bool) -> None:
        if dry_run:
            errors = self.game.rules.check_end_turn()
            self._raise_first_or_print_ok(errors)
        else:
            self.game.end_turn()

    def _raise_first_or_print_ok(self, errors: Iterable[Exception]) -> None:
        for e in errors:
            raise e
        print("Check passed: this action is legal, "
              "you can remove '?' and perform it")


def root_command(args: Namespace) -> None:
    """The function that is run after parsing the command line arguments."""
    import readline
    readline.set_completer_delims(" ")
    readline.set_completer(_autocomplete)
    readline.parse_and_bind("tab: complete")
    client = _Client(args)
    client.run()


def _main() -> None:
    """The entry point of `smawg.cli` command.

    Deprecated in favor of `smawg play`.
    """
    parser = argument_parser()
    assert isinstance(parser.description, str), "type narrowing for mypy"
    parser.description += "\n\nTHIS ENTRY POINT IS DEPRECATED, " \
                          "launch as 'python3 -m smawg play' instead"
    parser.formatter_class = RawDescriptionHelpFormatter
    args = parser.parse_args()
    root_command(args)


if __name__ == "__main__":
    _main()
