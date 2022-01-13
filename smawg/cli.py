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

from smawg import VERSION
from smawg.engine import Game, Data, RulesViolation


TITLE = f'Small World CLI v{VERSION}'
HELP_SUGGESTION = "Type 'help' to see available commands."
VISIT_HOME_PAGE = 'For more info, visit https://github.com/expurple/smawg'
START_SCREEN = '\n'.join([TITLE, HELP_SUGGESTION, VISIT_HOME_PAGE, ''])
HELP = '''\
Available commands:
    help            show this message
    show-players    show player stats
    show-combos     show available combos
    combo <index>   pick race+ability combo by index
    decline         enter decline
    end-turn        end your turn and give control to the next player
    quit            quit game

Press Tab for autocompletion.'''

COMMANDS = [line.strip().split()[0] for line in HELP.splitlines()[1:-2]]


def autocomplete(text: str, state: int) -> Optional[str]:
    """Command completer for `readline`."""
    results = [c for c in COMMANDS if c.startswith(text)]
    results.append(None)  # type:ignore
    return results[state]


def parse_args() -> Namespace:
    """Parse and return command line arguments.

    On error, print usage and exit.
    """
    parser = ArgumentParser(description=TITLE, epilog=VISIT_HOME_PAGE)
    parser.add_argument('data_file',
                        help='path to data.json')
    parser.add_argument('-p', '--players',
                        metavar='<num>',
                        type=int,
                        required=True,
                        help='specify the number of players')
    parser.add_argument('-s', '--no-shuffle',
                        action='store_true',
                        help="don't shuffle data from json")
    parser.add_argument('-d', '--read-dice',
                        action='store_true',
                        help='read dice roll results from stdin instead of '
                             'generating randomly')
    return parser.parse_args()


def init_game(args: Namespace, hooks: dict[str, Callable]) -> Game:
    """Construct `Game` with respect to command line `args`."""
    with open(args.data_file) as data_file:
        data_json = json.load(data_file)
    data = Data(data_json)
    if args.read_dice:
        return Game(data, args.players, not args.no_shuffle,
                    lambda: int(input("Enter the result of the dice roll: ")),
                    hooks=hooks)
    else:
        return Game(data, args.players, not args.no_shuffle,
                    hooks=hooks)


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
            print(f"Player {game.current_player_id} starts turn "
                  f"{game.current_turn}/{game.n_turns}.")

        def on_game_end(game: Game) -> None:
            self._command_show_players()
            print('')
            print(f"{game.n_turns} turns have passed, the game is over.")
            print("You can take a final look around and type 'quit' to quit.")

        hooks = {f.__name__: f for f in [on_turn_start, on_game_end]}
        self.game = init_game(args, hooks)

    def run(self) -> None:
        """Interpret user commands until stopped by `'quit'`, ^C or ^D."""
        try:
            self._run_main_loop()
        except (EOFError, KeyboardInterrupt):
            exit(1)

    def _run_main_loop(self) -> None:
        while True:
            try:
                command, *args = input('> ').strip().split()
                self._interpret(command, args)
            except InvalidCommand as e:
                print(f"Invalid command: {e.args[0]}")
                print(HELP_SUGGESTION)
            except RulesViolation as e:
                print(f"Rules violated: {e.args[0]}")

    def _interpret(self, command: str, args: list[str]) -> None:
        if command in COMMANDS and command != 'combo' and len(args) > 0:
            raise InvalidCommand(f"'{command}' does not accept any arguments.")
        if command == 'help':
            print(HELP)
        elif command == 'show-players':
            self._command_show_players()
        elif command == 'show-combos':
            self._command_show_combos()
        elif command == 'combo':
            self._command_combo(args)
        elif command == 'decline':
            self.game.decline()
        elif command == 'end-turn':
            self.game.end_turn()
        elif command == 'quit':
            exit(0)
        else:
            raise InvalidCommand(f"'{command}'.")

    def _command_show_players(self) -> None:
        headers = ['Player', 'Active ability', 'Active race', 'Declined race',
                   'Coins']
        rows = []
        for i, p in enumerate(self.game.players):
            rows.append([
                i,
                p.active_ability.name if p.active_ability else '-',
                p.active_race.name if p.active_race else '-',
                p.decline_race.name if p.decline_race else '-',
                p.coins
            ])
        print(tabulate(rows, headers, stralign='center', numalign='center'))

    def _command_show_combos(self) -> None:
        headers = ['Price', 'Coins you get', 'Ability', 'Race',
                   'Tokens you get']
        rows = [(i, c.coins, c.ability.name, c.race.name, c.base_n_tokens)
                for i, c in enumerate(self.game.combos)]
        print(tabulate(rows, headers, stralign='center', numalign='center'))

    def _command_combo(self, args: list[str]) -> None:
        if len(args) == 0:
            raise InvalidCommand('You need to provide a combo index.')
        if len(args) > 1:
            raise InvalidCommand("'combo' expects only one argument.")
        try:
            i = int(args[0])
            self.game.select_combo(i)
        except ValueError:
            raise InvalidCommand(f"'{args[0]}' is not a valid combo index.")


if __name__ == "__main__":
    readline.set_completer_delims(' ')
    readline.set_completer(autocomplete)
    readline.parse_and_bind("tab: complete")
    args = parse_args()
    client = Client(args)
    client.run()
