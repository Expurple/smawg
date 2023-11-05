#!/usr/bin/env python3

"""CLI client for Small World engine.

This module can serve as an example of how to use `smawg` library.

Running this module directly is deprecated, run it using `smawg play`.

See https://github.com/expurple/smawg for more info about the project.
"""


import json
import sys
from abc import ABC, abstractmethod
from argparse import ArgumentParser, Namespace, RawDescriptionHelpFormatter
from importlib import import_module
from pathlib import Path
from typing import Any, Type, assert_never

from pydantic import NonNegativeInt, TypeAdapter, ValidationError
from pydantic.dataclasses import dataclass
from tabulate import tabulate

from smawg import AbstractRules, Assets, Combo, Game, Player, RulesViolation
from smawg._metadata import PACKAGE_DIR, VERSION
from smawg.basic_rules import (
    Abandon, Conquer, ConquerWithDice, Decline, Deploy, EndTurn, SelectCombo,
    StartRedeployment
)
from smawg.default_rules import Action

__all__ = ["argument_parser", "root_command"]

# -----------------------------------------------------------------------------
#                              Global constants
# -----------------------------------------------------------------------------

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
    show-turn                  show the current turn and player

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
    "help", "quit", "show-combos", "show-players", "show-regions", "show-turn",
    "combo", "abandon", "conquer", "conquer-dice", "deploy", "redeploy",
    "decline", "end-turn"
]


# -----------------------------------------------------------------------------
#                              Command parsing
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class _Help:
    pass


@dataclass(frozen=True)
class _Quit:
    pass


@dataclass(frozen=True)
class _ShowCombos:
    pass


@dataclass(frozen=True)
class _ShowPlayers:
    pass


@dataclass(frozen=True)
class _ShowRegions:
    player: NonNegativeInt


@dataclass(frozen=True)
class _ShowTurn:
    pass


_NonActionCommand = \
    _Help | _Quit | _ShowCombos | _ShowPlayers | _ShowRegions | _ShowTurn
"""These commands don't support dry runs."""


@dataclass(frozen=True)
class _MaybeDry:
    dry_run: bool
    action: Action


_Command = _NonActionCommand | _MaybeDry


def _parse_command(line: str) -> _Command | None:
    """Parse a CLI `_Command` from string.

    Return `None` if the line is empty.

    Raise `ValueError` or `pydantic.ValidationError` if:
    * Command is unknown
    * Wrong number or arguments is given
    * A dry run is requested for command that doesn't support it
    * Some argument has invalid type or value
    """
    line = line.strip()
    dry_run = line.startswith("?")
    match line.removeprefix("?").strip().split():
        case []:
            return None
        case [command, *str_args]:
            # Pydantic will coerce and validate argument types for us.
            args: list[Any] = str_args
    match command:
        case "help" | "quit" | "show-combos" | "show-players" | "show-regions"\
                | "show-turn" if dry_run:
            raise ValueError(f"'{command}' does not support dry run mode")
        case "help":
            return _Help(*args)
        case "quit":
            return _Quit(*args)
        case "show-combos":
            return _ShowCombos(*args)
        case "show-players":
            return _ShowPlayers(*args)
        case "show-regions":
            return _ShowRegions(*args)
        case "show-turn":
            return _ShowTurn(*args)
        case "combo":
            return _MaybeDry(dry_run, SelectCombo(*args))
        case "abandon":
            return _MaybeDry(dry_run, Abandon(*args))
        case "conquer":
            return _MaybeDry(dry_run, Conquer(*args))
        case "conquer-dice":
            return _MaybeDry(dry_run, ConquerWithDice(*args))
        case "deploy":
            return _MaybeDry(dry_run, Deploy(*args))
        case "redeploy":
            return _MaybeDry(dry_run, StartRedeployment(*args))
        case "decline":
            return _MaybeDry(dry_run, Decline(*args))
        case "end-turn":
            return _MaybeDry(dry_run, EndTurn(*args))
    raise ValueError(f"unknown command '{command}'")


# -----------------------------------------------------------------------------
#                        The interactive interpreter
# -----------------------------------------------------------------------------

class _Client(ABC):
    """The interface for command line interaction styles."""

    @abstractmethod
    def __init__(self, game: Game) -> None:
        ...

    @abstractmethod
    def run(self) -> int:
        ...


def _autocomplete(text: str, state: int) -> str | None:
    """Command completer for `readline`."""
    results: list[str | None] = [c for c in _COMMANDS if c.startswith(text)]
    results.append(None)
    return results[state]


def _init_readline() -> None:
    import readline
    readline.set_completer_delims(" ")
    readline.set_completer(_autocomplete)
    readline.parse_and_bind("tab: complete")


def _read_dice_with_reenter() -> int:
    """Get result of a dice roll from an interactive console."""
    prompt = "Enter the result of the dice roll: "
    while True:
        try:
            return int(input(prompt))
        except ValueError:
            prompt = "The result must be an integer, try again: "


class _HumanClient(_Client):
    """Command line interactions with --style=human."""

    def __init__(self, game: Game) -> None:
        self.game = game
        self.player_of_last_command = -1  # Not equal to any actual player.
        self.reported_game_end = False

    def run(self) -> int:
        """Interpret user commands until stopped by `'quit'`, ^C or ^D.

        Return an exit code.
        """
        print(_START_SCREEN)
        _init_readline()
        try:
            return self._run_main_loop()
        except (EOFError, KeyboardInterrupt):
            return 1

    def _run_main_loop(self) -> int:
        """Return an exit code."""
        exit_code: int | None = None
        while exit_code is None:
            self._print_change_player_message()
            line = input("> ")
            try:
                command = _parse_command(line)
                if command is not None:
                    exit_code = self._execute(command)
            except ValidationError as e:
                print(f"Invalid command: {e}")
                print(_HELP_SUGGESTION)
            except ValueError as e:
                print(f"Invalid command: {e.args[0]}")
                print(_HELP_SUGGESTION)
            except RulesViolation as e:
                print(f"Rules violated: {e.args[0]}")
        return exit_code

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

    def _execute(self, command: _Command) -> int | None:
        """Execute the given `command`.

        Return an exit code if the command is `_Quit`, or `None` otherwise.

        Raise:
        * `ValueError`
            if some argument has invalid value.
        * `smawg.RulesViolation` subtypes
            if given command violates the game rules.
        """
        match command:
            case _Help():
                print(_HELP)
            case _Quit():
                return 0
            case _ShowCombos():
                self._command_show_combos()
            case _ShowPlayers():
                self._command_show_players()
            case _ShowRegions(player_id):
                self._command_show_regions(player_id)
            case _ShowTurn():
                self._command_show_turn()
            case _MaybeDry(False, ConquerWithDice(region)):
                self._command_conquer_dice(region)
            case _MaybeDry(False, action):
                self.game.do(action)
            case _MaybeDry(True, action):
                self._dry_run(action)
            case not_covered:
                # mypy 1.6.1 can't deduce `not_covered: Never` here.
                # When this is fixed in the pinned mypy, remove 'type:ignore'.
                assert_never(not_covered)  # type:ignore
        return None

    def _dry_run(self, action: Action) -> None:
        for e in self.game.rules.check(action):
            raise e  # Raise the first error, if any.
        print("Check passed: you can remove the '?' and perform this action")

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

    def _command_show_turn(self) -> Any:
        headers = [
            "Turn", "Player", "Is redeployment pseudo-turn?", "Game has ended?"
        ]
        row = [
            self.game.current_turn,
            self.game.player_id,
            "Yes" if self.game.is_in_redeployment_turn else "No",
            "Yes" if self.game.has_ended else "No",
        ]
        print(tabulate([row], headers, stralign="center", numalign="center"))

    def _command_conquer_dice(self, region: int) -> None:
        dice_value = self.game.conquer(region, use_dice=True)
        is_success = region in self.game.player.active_regions
        description = "successful" if is_success else "unsuccessful"
        print(f"Rolled {dice_value} on the dice, conquest was {description}.")


class _MachineClient(_Client):
    """Command line interactions with --style=machine."""

    def __init__(self, game: Game) -> None:
        self.game = game

    def run(self) -> int:
        """Interpret user commands until stopped by `'quit'`, ^C or ^D.

        Return an exit code.

        In contrast with `_HumanClient`, `EOFError` and `KeyboardInterrupt` are
        intentionally not caught and cause a crash.
        """
        _init_readline()  # Just in case, for manual testing.
        exit_code: int | None = None
        while exit_code is None:
            line = input()
            try:
                command = _parse_command(line)
                if command is None:
                    raise ValueError("no command provided")
                exit_code = self._execute(command)
            except ValidationError as e:
                # Workaround to serialize `ArgsKwargs`.
                # Straightforward `e.errors()` causes `json.dumps` to crash
                # when the `ValidationError` is caused by missing arguments.
                args = json.loads(e.json())
                error = {"type": e.__class__.__name__, "args": args}
                print(json.dumps({"error": error}))
            except (ValueError, RulesViolation) as e:
                error = {"type": e.__class__.__name__, "args": e.args}
                print(json.dumps({"error": error}))
        return exit_code

    def _execute(self, command: _Command) -> int | None:
        """Execute the given `command`.

        Return an exit code if the command is `_Quit`, or `None` otherwise.

        Raise:
        * `ValueError`
            if some argument has invalid value.
        * `smawg.RulesViolation` subtypes
            if given command violates the game rules.
        """
        result: Any
        match command:
            case _Help():
                result = _HELP
            case _Quit():
                return 0
            case _ShowCombos():
                result = self._command_show_combos()
            case _ShowPlayers():
                result = self._command_show_players()
            case _ShowRegions(player_id):
                result = self._command_show_regions(player_id)
            case _ShowTurn():
                result = self._command_show_turn()
            case _MaybeDry(False, action):
                result = self.game.do(action)
            case _MaybeDry(True, action):
                for e in self.game.rules.check(action):
                    raise e  # Raise the first error, if any.
                result = None
            case not_covered:
                # mypy 1.6.1 can't deduce `not_covered: Never` here.
                # When this is fixed in the pinned mypy, remove 'type:ignore'.
                assert_never(not_covered)  # type:ignore
        print(json.dumps({"result": result}))
        return None

    def _command_show_players(self) -> Any:
        return [
            TypeAdapter(Player).dump_python(p, mode="json")
            for p in self.game.players
        ]

    def _command_show_combos(self) -> Any:
        return [
            TypeAdapter(Combo).dump_python(c, mode="json")
            for c in self.game.combos
        ]

    def _command_show_regions(self, player_id: int) -> Any:
        if not 0 <= player_id < len(self.game.players):
            msg = f"<player> must be between 0 and {len(self.game.players)}"
            raise ValueError(msg)
        player = self.game.players[player_id]
        return TypeAdapter(Player).dump_python(
            player, mode="json", include={"active_regions", "decline_regions"}
        )

    def _command_show_turn(self) -> Any:
        return {
            "current_turn": self.game.current_turn,
            "player_id": self.game.player_id,
            "is_in_redeployment_turn": self.game.is_in_redeployment_turn,
            "game_has_ended": self.game.has_ended,
        }


# -----------------------------------------------------------------------------
#                    Argument parsing and the entry point
# -----------------------------------------------------------------------------

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
        "--style",
        choices=["human", "machine"],
        default="human",
        help="set the output style (see docs/style.md for details)",
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


def _init_assets(assets_file: str, relative_path: bool, no_shuffle: bool
                 ) -> Assets:
    """Initialize assets with respect to command line arguments."""
    if relative_path:
        assets_file = f"{PACKAGE_DIR}/{assets_file}"
    with open(assets_file) as file:
        assets_json = json.load(file)
    assets: Assets = TypeAdapter(Assets).validate_python(assets_json)
    if not no_shuffle:
        assets = assets.shuffle()
    return assets


def _import_rules(filename: str) -> Type[AbstractRules[Action]]:
    """Dynamically load `Rules` from a Python file."""
    rules_file_path = Path(filename).resolve()
    rules_file_name = rules_file_path.name
    rules_dir_name = str(rules_file_path.parent)
    sys.path.append(rules_dir_name)
    rules_module = import_module(rules_file_name[:-3])
    rules: Type[AbstractRules[Action]] = rules_module.Rules
    return rules


def root_command(args: Namespace) -> None:
    """The function that is run after parsing the command line arguments."""
    assets = _init_assets(
        args.assets_file, args.relative_path, args.no_shuffle
    )
    rules = _import_rules(args.rules)
    client_type: Type[_Client]
    match args.style:
        case "human":
            roll_dice = _read_dice_with_reenter
            client_type = _HumanClient
        case "machine":
            roll_dice = lambda: int(input())  # noqa
            client_type = _MachineClient
        case _:
            assert False, "invalid styles should be caught by argparse"
    if args.read_dice:
        game = Game(assets, rules, dice_roll_func=roll_dice)
    else:
        game = Game(assets, rules)
    client = client_type(game)
    exit_code = client.run()
    sys.exit(exit_code)


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
