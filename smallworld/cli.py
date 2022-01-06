'''CLI client for Small World engine.
See https://github.com/expurple/smallworld for more info.'''

import json
import readline
from argparse import ArgumentParser, Namespace
from typing import Callable, Optional

from smallworld.engine import Game, Data, RulesViolation


DESCRIPTION = '''\
Small World CLI
For more info, visit https://github.com/expurple/smallworld'''

HELP_SUGGESTION = "Type 'help' to see available commands."

HELP = '''\
Available commands:
    help          show this message
    show-players  show player stats
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


def init_game(args: Namespace, hooks: dict[str, Callable]) -> Game:
    '''Construct `Game` with respect to command line `args`.'''
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
    pass


class Client:
    '''Handles console IO.'''

    def __init__(self, args: Namespace) -> None:
        # This print originally was in `run()`, but now `init_game()` prints
        # because of `Game` hooks, and this print needs to be above that...
        print(DESCRIPTION + '\n\n' + HELP_SUGGESTION)

        def on_turn_start(game: Game) -> None:
            print(f"Player {game.current_player_id} starts turn "
                  f"{game.current_turn}/{game.n_turns}.")

        def on_game_end(game: Game) -> None:
            print(f"{game.n_turns} turns have passed, the game is over.")

        hooks = {f.__name__: f for f in [on_turn_start, on_game_end]}
        self.game = init_game(args, hooks)

    def run(self) -> None:
        '''Interpret user commands until stopped by `'quit'`, ^C or ^D.'''
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
        if command in COMMANDS and command != 'race' and len(args) > 0:
            raise InvalidCommand(f"'{command}' does not accept any arguments.")
        if command == 'help':
            print(HELP)
        elif command == 'show-players':
            self._command_show_players()
        elif command == 'race':
            self._command_race(args)
        elif command == 'decline':
            self.game.decline()
        elif command == 'end':
            self.game.end_turn()
        elif command == 'quit':
            exit(0)
        else:
            raise InvalidCommand(f"Unknown command: '{command}'.")

    def _command_show_players(self) -> None:
        def print_row(*values):
            print("{:^6}  {:^14}  {:^11}  {:^11}  {:>5}".format(*values))

        headers = ['Player', 'Active ability', 'Active race', 'Declined race',
                   'Coins']
        print_row(*headers)
        print_row(*['-' * len(h) for h in headers])
        for i, p in enumerate(self.game.players):
            print_row(
                i,
                p.active_ability.name if p.active_ability else '-',
                p.active_race.name if p.active_race else '-',
                p.decline_race.name if p.decline_race else '-',
                p.coins
            )

    def _command_race(self, args: list[str]) -> None:
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
