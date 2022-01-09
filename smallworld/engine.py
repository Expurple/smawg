'''Backend engine for Small World board game.
See https://github.com/expurple/smallworld for more info.'''

import random
from collections import defaultdict
from copy import deepcopy
from functools import wraps
from itertools import islice
from typing import Callable, Mapping, Optional


# -------------------------- "dumb" data objects ------------------------------

class Data:
    '''Storage for immutable game properties: constants like the total amount
    of turns, lists of available races and abilities, etc.'''

    def __init__(self, json: dict) -> None:
        '''Construct strongly typed `Data` from json object.'''
        assert isinstance(json["min_n_players"], int)
        assert isinstance(json["max_n_players"], int)
        assert isinstance(json["n_selectable_combos"], int)
        assert isinstance(json["n_turns"], int)
        assert isinstance(json["abilities"], list)
        assert isinstance(json["races"], list)
        self.min_n_players: int = json["min_n_players"]
        self.max_n_players: int = json["max_n_players"]
        self.n_selectable_combos: int = json["n_selectable_combos"]
        self.n_turns: int = json["n_turns"]
        self.abilities = [Ability(obj) for obj in json["abilities"]]
        self.races = [Race(obj) for obj in json["races"]]


class Ability:
    '''Immutable description of an ability (just like on a physical banner).'''

    def __init__(self, json: dict) -> None:
        '''Construct strongly typed `Ability` from json object.'''
        assert isinstance(json["name"], str)
        assert isinstance(json["n_tokens"], int)
        self.name: str = json["name"]
        self.n_tokens: int = json["n_tokens"]


class Race:
    '''Immutable description of a race (just like on a physical banner).'''

    def __init__(self, json: dict) -> None:
        '''Construct strongly typed `Race` from json object.'''
        assert isinstance(json["name"], str)
        assert isinstance(json["n_tokens"], int)
        assert isinstance(json["max_n_tokens"], int)
        self.name: str = json["name"]
        self.n_tokens: int = json["n_tokens"]
        self.max_n_tokens: int = json["max_n_tokens"]


class Combo:
    '''Immutable pair of `Race` and `Ability` banners, with a few `coins`
    dynamically thrown on top.'''

    def __init__(self, race: Race, ability: Ability) -> None:
        '''Construct a freshly revealed `Race`+`Ability` combo.'''
        self.race = race
        self.ability = ability
        self.base_n_tokens = race.n_tokens + ability.n_tokens
        self.coins: int = 0


class Player:
    '''A bunch of "dumb" mutable stats, related to the same player.'''

    def __init__(self, coins: int) -> None:
        '''Initialize `Player` with an initial supply of `coins`.'''
        self.active_race: Optional[Race] = None
        self.active_ability: Optional[Ability] = None
        self.decline_race: Optional[Race] = None
        self.decline_ability: Optional[Ability] = None
        self.acted_on_this_turn: bool = False
        self.declined_on_this_turn: bool = False
        self.coins = coins

    def needs_to_pick_combo(self) -> bool:
        return self.is_in_decline() and not self.declined_on_this_turn

    def is_in_decline(self) -> bool:
        return self.active_race is None

    def decline(self) -> None:
        self.decline_race = self.active_race
        self.decline_ability = self.active_ability
        self.active_race = None
        self.active_ability = None
        self.declined_on_this_turn = True

    def set_active(self, combo: Combo) -> None:
        self.active_race = combo.race
        self.active_ability = combo.ability


class Token:
    '''Dummy class for race tokens.'''
    pass


# ------------------------ randomization utilities ----------------------------

def shuffle(data: Data) -> Data:
    '''Shuffles the game data (e.g. race order), just like you would in a
    physical Small World game.'''
    data = deepcopy(data)
    random.shuffle(data.races)
    random.shuffle(data.abilities)
    return data


def roll_dice() -> int:
    '''Default function for random dice roll outcomes.'''
    return random.choice((0, 0, 0, 1, 2, 3))


# --------------------- the Small World engine itself -------------------------

def create_tokens_supply(races: list[Race]):
    tokens_supply = dict[Race, list[Token]]()
    for race in races:
        tokens_supply[race] = [Token() for _ in range(race.max_n_tokens)]
    return tokens_supply


def do_nothing(*args, **kwargs):
    '''Empty placeholder for missing hooks.'''
    pass


class RulesViolation(Exception):
    pass


def check_rules(require_active: bool = False):
    '''Adds boilerplate rule checks to public `Game` methods.'''
    def decorator(game_method: Callable):
        @wraps(game_method)
        def wrapper(*args, **kwargs):
            # Perform necessary checks
            self: "Game" = args[0]
            if self.current_turn >= self.n_turns:
                msg = "The game is over, you shouldn't do anything anymore"
                raise RulesViolation(msg)
            if require_active and self._current_player.is_in_decline():
                msg = "To do this, you need to control an active race"
                raise RulesViolation(msg)
            # And then just execute the wrapped method
            return game_method(*args, **kwargs)
        return wrapper
    return decorator


class Game:
    '''Encapsulates and manages the game state. Provides high-level API for
    performing in-game actions and getting current stats.

    Methods represent in-game actions and throw `RulesViolation` when an
    action violates the rules.

    Data members represent the game state and are designed to be read, but not
    modified.'''

    def __init__(self, data: Data, n_players: int, shuffle_data: bool = True,
                 dice_roll_func: Callable[[], int] = roll_dice,
                 hooks: Mapping[str, Callable] = dict()
                 ) -> None:
        '''Initialize the game state for `n_players`, based on `data`.

        Provide `shuffle_data=False` to preserve the known order of races and
        powers.

        Provide custom `dice_roll_func` to get pre-determined (or even
        dynamically decided) dice roll results.

        Provide optional `hooks` to automatically fire on certain events.
        For detailed info, see `docs/hooks.md`'''

        if not data.min_n_players <= n_players <= data.max_n_players:
            msg = f"Invalid number of players: {n_players} (expected " \
                  f"between {data.min_n_players} and {data.max_n_players})"
            raise RulesViolation(msg)
        if shuffle_data:
            data = shuffle(data)
        self._abilities = data.abilities
        self._races = data.races
        self._n_combos = data.n_selectable_combos
        self.n_turns = data.n_turns
        self.current_turn: int = 0
        visible_ra = islice(zip(self._races, self._abilities), self._n_combos)
        self.combos = [Combo(r, a) for r, a in visible_ra]
        self.players = [Player(self._n_combos - 1) for _ in range(n_players)]
        self.current_player_id: int = 0
        self._current_player = self.players[self.current_player_id]
        self.tokens_supply = create_tokens_supply(self._races)
        self.roll_dice = dice_roll_func
        self._hooks: Mapping[str, Callable] \
            = defaultdict(lambda: do_nothing, **hooks)
        self._hooks["on_turn_start"](self)

    @check_rules(require_active=True)
    def decline(self) -> None:
        '''Put your active race in decline state.'''
        if self._current_player.acted_on_this_turn:
            msg = "You've already used your active race during this turn. " \
                  "You'll have to decline during the next turn"
            raise RulesViolation(msg)
        self._current_player.decline()

    @check_rules()
    def select_combo(self, combo_index: int) -> None:
        '''Pick the combo at specified `combo_index` as active.'''
        if not self._current_player.is_in_decline():
            raise RulesViolation("You need to decline first")
        if self._current_player.declined_on_this_turn:
            raise RulesViolation("You need to finish your turn now and select "
                                 "a new race during the next turn")
        self._pay_for_combo(combo_index)
        self._current_player.set_active(self.combos[combo_index])
        self._rotate_combos(combo_index)
        self._current_player.acted_on_this_turn = True

    @check_rules()
    def end_turn(self) -> None:
        '''Receive coins for the passed turn and give control to the next
        player.'''
        if self._current_player.needs_to_pick_combo():
            raise RulesViolation("You need to select a new race+ability combo "
                                 "before ending this turn")
        self._hooks["on_turn_end"](self)
        self._switch_player()
        if self.current_turn < self.n_turns:
            self._hooks["on_turn_start"](self)
        else:
            self._hooks["on_game_end"](self)

    def _pay_for_combo(self, combo_index: int) -> None:
        combos_above = self.combos[:combo_index]
        coins_getting = sum(c.coins for c in combos_above)
        if combo_index > self._current_player.coins + coins_getting:
            raise RulesViolation("Not enough coins, select a different race")
        self._current_player.coins += coins_getting - combo_index
        for combo in combos_above:
            combo.coins += 1
        self.combos[combo_index].coins = 0

    def _rotate_combos(self, combo_index: int) -> None:
        chosen_race = self._races.pop(combo_index)
        chosen_ability = self._abilities.pop(combo_index)
        self._races.append(chosen_race)
        self._abilities.append(chosen_ability)
        self.combos.pop(combo_index)
        next_combo = Combo(self._races[self._n_combos-1],
                           self._abilities[self._n_combos-1])
        self.combos.append(next_combo)

    def _switch_player(self) -> None:
        self.current_player_id += 1
        if self.current_player_id == len(self.players):
            self.current_player_id = 0
            self.current_turn += 1
        self._current_player = self.players[self.current_player_id]
        self._current_player.acted_on_this_turn = False
        self._current_player.declined_on_this_turn = False
