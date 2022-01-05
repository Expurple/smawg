'''CLI client for Small World engine.
See https://github.com/expurple/smallworld for more info.'''

import json
import readline
from argparse import ArgumentParser, Namespace
from typing import Optional

from smallworld.engine import Game, Data, RulesViolation


DESCRIPTION = '''\
Small World CLI
For more info, visit https://github.com/expurple/smallworld'''

HELP_SUGGESTION = "Type 'help' to see available commands."

HELP = '''\
Available commands:
    help          show this message
    race <index>  pick race+ability combo by index
    decline       enter decline
    end           end turn
    quit          quit game

Press Tab for autocompletion.'''

COMMANDS = [line.strip().split()[0] for line in HELP.splitlines()[1:-2]]


def autocomplete(text: str, state: int) -> Optional[str]:
    '''Command completer for `readline`.'''
    results = [c for c in COMMANDS if c.startswith(text)]
    results.append(None)  # type:ignore
    return results[state]


def parse_args() -> Namespace:
    parser = ArgumentParser(description=DESCRIPTION)
    parser.add_argument('data_file',
                        help='path to data.json')
    parser.add_argument('-p', '--players',
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


def init_game(args: Namespace) -> Game:
    '''Construct `Game` with respect to command line `args`.'''
    with open(args.data_file) as data_file:
        data_json = json.load(data_file)
    data = Data(data_json)
    if args.read_dice:
        return Game(data, args.players, not args.no_shuffle,
                    lambda: int(input("Enter the result of the dice roll: ")))
    else:
        return Game(data, args.players, not args.no_shuffle)


class InvalidCommand(ValueError):
    pass


class Client:
    '''Handles console IO.'''

    def __init__(self, args) -> None:
        self.game = init_game(args)

    def run(self) -> None:
        '''Interpret user commands until stopped by `'quit'`, ^C or ^D.'''
        print(DESCRIPTION)
        print('')
        print(HELP_SUGGESTION)
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
        if command in ('help', 'decline', 'end', 'quit') and len(args) > 0:
            raise InvalidCommand(f"'{command}' does not accept any arguments.")
        if command == 'help':
            print(HELP)
        elif command == 'race':
            self._interpret_race(args)
        elif command == 'decline':
            self.game.decline()
        elif command == 'end':
            self.game.end_turn()
        elif command == 'quit':
            exit(0)
        else:
            raise InvalidCommand(f"Unknown command: '{command}'.")

    def _interpret_race(self, args: list[str]) -> None:
        if len(args) == 0:
            raise InvalidCommand('You need to provide a race index.')
        try:
            i = int(args[0])
            self.game.select_combo(i)
        except ValueError:
            raise InvalidCommand(f"'{args[0]}' is not a valid race index.")


if __name__ == "__main__":
    readline.set_completer(autocomplete)
    readline.parse_and_bind("tab: complete")
    args = parse_args()
    client = Client(args)
    client.run()
