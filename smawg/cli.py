#!/usr/bin/env python3

"""CLI client for Small World engine.

The internals aren't stable
and aren't supposed to be imported by anything but `smawg.tests`.

Although, this module can serve as an example of how to use `smawg.engine`.

See https://github.com/expurple/smawg for more info about the project.
"""


import json
import readline
from argparse import ArgumentParser, Namespace
from typing import Callable, Optional

from tabulate import tabulate

from smawg import _PACKAGE_DIR, VERSION
from smawg.engine import Game, RulesViolation


TITLE = f"smawg CLI v{VERSION}"
HELP_SUGGESTION = "Type 'help' to see available commands."
VISIT_HOME_PAGE = "For more info, visit https://github.com/expurple/smawg"
START_SCREEN = "\n".join([TITLE, HELP_SUGGESTION, VISIT_HOME_PAGE, ""])
HELP = """\
Available commands:
    help                   show this message
    show-combos            show available combos
    show-players           show general player stats
    show-regions <player>  show regions owned by <player>
    combo <index>          pick race+ability combo by <index>
    conquer <region>       conquer <region> by index
    conquer-dice <region>  conquer <region>, using the reinforcements dice
    deploy <n> <region>    deploy <n> tokens from hand to <region>
    redeploy               pick up tokens, leaving 1 in each region
    decline                enter decline
    end-turn               end turn and give control to the next player
    quit                   quit game

Press Tab for autocompletion."""

COMMAND_DESCRIPTIONS = [line.strip() for line in HELP.splitlines()[1:-2]]
COMMANDS = [d.split()[0] for d in COMMAND_DESCRIPTIONS]
COMMANDS_WITHOUT_ARGS = [c for c, d in zip(COMMANDS, COMMAND_DESCRIPTIONS)
                         if "<" not in d]


def autocomplete(text: str, state: int) -> Optional[str]:
    """Command completer for `readline`."""
    results: list[Optional[str]] = [c for c in COMMANDS if c.startswith(text)]
    results.append(None)
    return results[state]


def parse_args() -> Namespace:
    """Parse and return command line arguments.

    On error, print usage and exit.
    """
    parser = ArgumentParser(description=TITLE, epilog=VISIT_HOME_PAGE)
    parser.add_argument("assets_file",
                        metavar="<assets_file>",
                        help="path to JSON file with assets")
    parser.add_argument("-s", "--no-shuffle",
                        action="store_true",
                        help="don't shuffle data from <assets_file>")
    parser.add_argument("-d", "--read-dice",
                        action="store_true",
                        help="read dice roll results from stdin instead of "
                             "generating randomly")
    parser.add_argument("-r", "--relative-path",
                        action="store_true",
                        help="search for `assets_file` inside of `smawg` "
                             "package directory")
    return parser.parse_args()


def read_dice() -> int:
    """Get result of a dice roll from an interactive console."""
    prompt = "Enter the result of the dice roll: "
    while True:
        try:
            return int(input(prompt))
        except ValueError:
            prompt = "The result must be an integer, try again: "


def init_game(args: Namespace, hooks: dict[str, Callable]) -> Game:
    """Construct `Game` with respect to command line `args`."""
    if args.relative_path:
        args.assets_file = f"{_PACKAGE_DIR}/{args.assets_file}"
    with open(args.assets_file) as file:
        assets = json.load(file)
    if args.read_dice:
        return Game(assets, shuffle_data=not args.no_shuffle,
                    dice_roll_func=read_dice, hooks=hooks)
    else:
        return Game(assets, shuffle_data=not args.no_shuffle, hooks=hooks)


class InvalidCommand(ValueError):
    """Exception raised in `Client` when an invalid command is entered."""

    pass


class Client:
    """Handles console IO."""

    def __init__(self, args: Namespace) -> None:
        """Construct `Client` with respect to command line `args`."""
        # This print originally was in `run()`, but now `init_game()` prints
        # because of `Game` hooks, and this print needs to be above that...
        print(START_SCREEN)

        def on_turn_start(game: Game) -> None:
            print(f"Player {game.player_id} starts turn "
                  f"{game.current_turn}/{game.n_turns}.")

        def on_redeploy(game: Game) -> None:
            print(f"Player {game.player_id} redeploys "
                  f"{game.player.tokens_on_hand} tokens.")

        def on_game_end(game: Game) -> None:
            self._command_show_players()
            print("")
            print(f"{game.n_turns} turns have passed, the game is over.")
            print("You can take a final look around and type 'quit' to quit.")

        hooks = {
            "on_turn_start": on_turn_start,
            "on_redeploy": on_redeploy,
            "on_game_end": on_game_end
        }
        self.game = init_game(args, hooks)

    def run(self) -> None:
        """Interpret user commands until stopped by `'quit'`, ^C or ^D."""
        try:
            self._run_main_loop()
        except (EOFError, KeyboardInterrupt):
            exit(1)

    def _run_main_loop(self) -> None:
        while True:
            command = input("> ").strip()
            if command == "":
                continue
            command, *args = command.split()
            try:
                self._interpret(command, args)
            except InvalidCommand as e:
                print(f"Invalid command: {e.args[0]}")
                print(HELP_SUGGESTION)
            except ValueError as e:
                print(f"Invalid argument: {e.args[0]}")
            except RulesViolation as e:
                print(f"Rules violated: {e.args[0]}")

    def _interpret(self, command: str, args: list[str]) -> None:
        """Interpret and execute the given `command`.

        Raise:
        * `InvalidCommand` - if an unkown `command` or wrong number of `args`
            is given.
        * `ValueError` - if some argument has invalid type or value.
        * `RulesViolation` - if given command violates the game rules.
        """
        if command in COMMANDS_WITHOUT_ARGS and len(args) > 0:
            raise InvalidCommand(f"'{command}' does not accept any arguments")
        if command == "help":
            print(HELP)
        elif command == "show-combos":
            self._command_show_combos()
        elif command == "show-players":
            self._command_show_players()
        elif command == "show-regions":
            self._command_show_regions(args)
        elif command == "combo":
            self._command_combo(args)
        elif command == "conquer":
            self._command_conquer(args)
        elif command == "conquer-dice":
            self._command_conquer_dice(args)
        elif command == "deploy":
            self._command_deploy(args)
        elif command == "decline":
            self.game.decline()
        elif command == "redeploy":
            self.game.start_redeployment()
        elif command == "end-turn":
            self.game.end_turn()
        elif command == "quit":
            exit(0)
        else:
            raise InvalidCommand(f"'{command}'")

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

    def _command_show_regions(self, args: list[str]) -> None:
        i = self._parse_ints(args, n=1)[0]
        if not 0 <= i < len(self.game.players):
            msg = f"<player> must be between 0 and {len(self.game.players)}"
            raise ValueError(msg)
        headers = ["Region", "Tokens", "Type"]
        rows = []
        for r, t in self.game.players[i].active_regions.items():
            rows.append([r, t, "Active"])
        for r in self.game.players[i].decline_regions:
            rows.append([r, 1, "Declined"])
        print(tabulate(rows, headers, stralign="center", numalign="center"))

    def _command_combo(self, args: list[str]) -> None:
        i = self._parse_ints(args, n=1)[0]
        self.game.select_combo(i)

    def _command_conquer(self, args: list[str]) -> None:
        i = self._parse_ints(args, n=1)[0]
        self.game.conquer(i)

    def _command_conquer_dice(self, args: list[str]) -> None:
        i = self._parse_ints(args, n=1)[0]
        self.game.conquer(i, use_dice=True)

    def _command_deploy(self, args: list[str]) -> None:
        n, region = self._parse_ints(args, n=2)
        self.game.deploy(n, region)

    def _parse_ints(self, args: list[str], *, n: int) -> list[int]:
        """Parse `args` as a list of `n` integers."""
        if len(args) != n:
            msg = f"expected {n} argument(s), but got {len(args)}"
            raise InvalidCommand(msg)
        return [self._parse_int(a) for a in args]

    def _parse_int(self, s: str) -> int:
        """Parse an integer or raise `ValueError` with a frendly message."""
        try:
            return int(s)
        except ValueError:
            raise ValueError(f"'{s}' is not an integer")


if __name__ == "__main__":
    readline.set_completer_delims(" ")
    readline.set_completer(autocomplete)
    readline.parse_and_bind("tab: complete")
    args = parse_args()
    client = Client(args)
    client.run()
