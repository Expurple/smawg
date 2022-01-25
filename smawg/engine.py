"""Backend engine for Small World board game.

See https://github.com/expurple/smawg for more info.
"""

import json
import random
from collections import defaultdict
from copy import deepcopy
from functools import wraps
from itertools import islice
from typing import Callable, Mapping, Optional

import jsonschema

from smawg import _SCHEMA_DIR


# ------------------------ JSON schemas for assets ----------------------------

_JS_REF_RESOLVER = jsonschema.RefResolver(f"file://{_SCHEMA_DIR}/", None)
"""Fixes references to local schemas.

Should be used in every `jsonschema.validate()` call.
"""

with open(f"{_SCHEMA_DIR}/assets.json") as file:
    ASSETS_SCHEMA: dict = json.load(file)

with open(f"{_SCHEMA_DIR}/ability.json") as file:
    ABILITY_SCHEMA: dict = json.load(file)

with open(f"{_SCHEMA_DIR}/race.json") as file:
    RACE_SCHEMA: dict = json.load(file)


# -------------------------- "dumb" data objects ------------------------------

class Ability:
    """Immutable description of an ability (just like on a physical banner)."""

    def __init__(self, json: dict) -> None:
        """Construct strongly typed `Ability` from json object.

        Raise `jsonschema.exceptions.ValidationError`
        if `json` doesn't match `assets_schema/ability.json`.
        """
        jsonschema.validate(json, ABILITY_SCHEMA, resolver=_JS_REF_RESOLVER)
        self.name: str = json["name"]
        self.n_tokens: int = json["n_tokens"]


class Race:
    """Immutable description of a race (just like on a physical banner)."""

    def __init__(self, json: dict) -> None:
        """Construct strongly typed `Race` from json object.

        Raise `jsonschema.exceptions.ValidationError`
        if `json` doesn't match `assets_schema/race.json`.
        """
        jsonschema.validate(json, RACE_SCHEMA, resolver=_JS_REF_RESOLVER)
        self.name: str = json["name"]
        self.n_tokens: int = json["n_tokens"]
        self.max_n_tokens: int = json["max_n_tokens"]


class Combo:
    """Immutable pair of `Race` and `Ability` banners.

    Also contains a mutable amount of `coins` put on top during the game.
    """

    def __init__(self, race: Race, ability: Ability) -> None:
        """Construct a freshly revealed `Race`+`Ability` combo."""
        self.race = race
        self.ability = ability
        self.base_n_tokens = race.n_tokens + ability.n_tokens
        self.coins: int = 0


class Player:
    """A bunch of "dumb" mutable stats, related to the same player."""

    def __init__(self, coins: int) -> None:
        """Initialize `Player` with an initial supply of `coins`."""
        self.active_race: Optional[Race] = None
        self.active_ability: Optional[Ability] = None
        self.decline_race: Optional[Race] = None
        self.decline_ability: Optional[Ability] = None
        self.acted_on_this_turn: bool = False
        self.declined_on_this_turn: bool = False
        self.coins = coins

    def needs_to_pick_combo(self) -> bool:
        """Check if `Player` must select a combo during the current turn."""
        return self.is_in_decline() and not self.declined_on_this_turn

    def is_in_decline(self) -> bool:
        """Check if `Player` is in decline state."""
        return self.active_race is None

    def _decline(self) -> None:
        """Put `Player`'s active race in decline state."""
        self.decline_race = self.active_race
        self.decline_ability = self.active_ability
        self.active_race = None
        self.active_ability = None
        self.declined_on_this_turn = True

    def _set_active(self, combo: Combo) -> None:
        """Set `Race` and `Ability` from the given `combo` as active."""
        self.active_race = combo.race
        self.active_ability = combo.ability


class Token:
    """Dummy class for race tokens."""

    pass


# ------------------------ randomization utilities ----------------------------

def shuffle(assets: dict) -> dict:
    """Shuffle the order of `Race` and `Ability` banners in `assets`.

    Just like you would do in a physical Small World game.
    """
    assets = deepcopy(assets)
    random.shuffle(assets["races"])
    random.shuffle(assets["abilities"])
    return assets


def roll_dice() -> int:
    """Return a random dice roll result."""
    return random.choice((0, 0, 0, 1, 2, 3))


# --------------------- the Small World engine itself -------------------------

def _create_tokens_supply(races: list[Race]):
    """Generate a supply of `Token`s for each `Race` in `races`."""
    tokens_supply = dict[Race, list[Token]]()
    for race in races:
        tokens_supply[race] = [Token() for _ in range(race.max_n_tokens)]
    return tokens_supply


def _do_nothing(*args, **kwargs) -> None:
    """Just accept any arguments and do nothing."""
    pass


class RulesViolation(Exception):
    """Exception raised from `Game` methods when rules are violated."""

    pass


class GameEnded(RulesViolation):
    """Exception raised from `Game` methods when calling after the game end."""

    def __init__(self, *args) -> None:
        """Construct an exception with default `GameEnded` message."""
        msg = "The game is over, this action is not available anymore"
        super().__init__(msg, *args)


def _check_rules(require_active: bool = False):
    """Add boilerplate rule checks to public `Game` methods.

    `require_active` specifies whether an action requires an active race.
    """
    def decorator(game_method: Callable):
        @wraps(game_method)
        def wrapper(*args, **kwargs):
            # Perform necessary checks
            self: "Game" = args[0]
            if self.has_ended:
                raise GameEnded()
            if require_active and self._current_player.is_in_decline():
                msg = "To do this, you need to control an active race"
                raise RulesViolation(msg)
            # And then just execute the wrapped method
            return game_method(*args, **kwargs)
        return wrapper
    return decorator


class Game:
    """High-level representation of a single Small World game.

    Provides:
    * Flexible configuration on construction (see `__init__`).
    * API for performing in-game actions (as methods).
    * Access to the game state (as readonly properties).

    Method calls automatically update `Game` state according to the rules,
    or raise exceptions if the call violates the rules.
    """

    def __init__(self, assets: dict, n_players: int, shuffle_data: bool = True,
                 dice_roll_func: Callable[[], int] = roll_dice,
                 hooks: Mapping[str, Callable] = dict()) -> None:
        """Initialize a game for `n_players`, with given `assets`.

        When initialization is finished, the object is ready to be used by
        player 0. `"on_turn_start"` hook is fired immediately, if provided.

        Provide `shuffle_data=False` to preserve
        the known order of races and ablities in `assets`.

        Provide custom `dice_roll_func` to get pre-determined
        (or even dynamically decided) dice roll results.

        Provide optional `hooks` to automatically fire on certain events.
        For details, see `docs/hooks.md`

        Exceptions raised:
        * `jsonschema.exceptions.ValidationError` -
            if `assets` dict doesn't match `assets_schema/assets.json`.
        * `RulesViolation` -
            if `n_players` doesn't respect the limits specified in `assets`.
        """
        jsonschema.validate(assets, ASSETS_SCHEMA, resolver=_JS_REF_RESOLVER)
        if not assets["min_n_players"] <= n_players <= assets["max_n_players"]:
            msg = f"Invalid number of players: {n_players} (expected " \
                  f'between {assets["min_n_players"]} ' \
                  f'and {assets["max_n_players"]})'
            raise RulesViolation(msg)
        if shuffle_data:
            assets = shuffle(assets)
        self._abilities = [Ability(a) for a in assets["abilities"]]
        self._races = [Race(r) for r in assets["races"]]
        self._n_combos: int = assets["n_selectable_combos"]
        self._n_turns: int = assets["n_turns"]
        self._current_turn: int = 1
        visible_ra = islice(zip(self._races, self._abilities), self._n_combos)
        self._combos = [Combo(r, a) for r, a in visible_ra]
        self._players = [Player(self._n_combos - 1) for _ in range(n_players)]
        self._current_player_id: int = 0
        self._current_player = self.players[self.current_player_id]
        self._tokens_supply = _create_tokens_supply(self._races)
        self._roll_dice = dice_roll_func
        self._hooks: Mapping[str, Callable] \
            = defaultdict(lambda: _do_nothing, **hooks)
        self._hooks["on_turn_start"](self)

    @property
    def n_turns(self) -> int:
        """The total number of turns in the `Game`.

        After the last turn is finished, the `Game` ends.
        """
        return self._n_turns

    @property
    def current_turn(self) -> int:
        """The number of the current turn (starting on `1`)."""
        return self._current_turn

    @property
    def has_ended(self) -> bool:
        """Indicates whether the game has already ended.

        If this is `True`, all methods raise `GameEnded`.
        """
        return self.current_turn > self.n_turns

    @property
    def combos(self) -> list[Combo]:
        """The list of race+ability combos available to be selected."""
        return self._combos

    @property
    def players(self) -> list[Player]:
        """Stats for every player, accessed with a 0-based player_id."""
        return self._players

    @property
    def current_player_id(self) -> int:
        """0-based index of the current active player in `players`."""
        return self._current_player_id

    @_check_rules(require_active=True)
    def decline(self) -> None:
        """Put player's active race in decline state.

        Exceptions raised:
        * `RulesViolation` - if the player is already in decline
            or has already used his active race during this turn.
        * `GameEnded` - if this method is called after the game has ended.
        """
        if self._current_player.acted_on_this_turn:
            msg = "You've already used your active race during this turn. " \
                  "You can only decline during the next turn"
            raise RulesViolation(msg)
        self._current_player._decline()

    @_check_rules()
    def select_combo(self, combo_index: int) -> None:
        """Select the combo at specified `combo_index` as active.

        During that:
        * The player gets all coins that have been put on that combo.
        * Puts 1 coin on each combo above that (`combo_index` coins in total).
        * Then, the next combo is revealed.

        Exceptions raised:
        * `RulesViolation` - if the player is not in decline, or has
            just declined during this turn, or doesn't have enough coins.
        * `GameEnded` - if this method is called after the game has ended.
        """
        assert 0 <= combo_index < len(self.combos)
        if not self._current_player.is_in_decline():
            raise RulesViolation("You need to decline first")
        if self._current_player.declined_on_this_turn:
            raise RulesViolation("You need to finish your turn now and select "
                                 "a new race during the next turn")
        self._pay_for_combo(combo_index)
        self._current_player._set_active(self.combos[combo_index])
        self._pop_combo(combo_index)
        self._current_player.acted_on_this_turn = True

    @_check_rules()
    def end_turn(self) -> None:
        """End current player's turn and give control to the next player.

        This action:
        * Fires `"on_turn_end"` hook.
        * Then updates `current_player_id`.
        * If that was the last player, increments `current_turn`.
        * Then fires `"on_turn_start"` or `"on_game_end"` hook,
            depending on whether `Game.has_ended`.

        Exceptions raised:
        * `RulesViolation` - if the player must select a new combo
        during the current turn and haven't done that yet.
        * `GameEnded` - if this method is called after the game has ended.
        """
        if self._current_player.needs_to_pick_combo():
            raise RulesViolation("You need to select a new race+ability combo "
                                 "before ending this turn")
        self._hooks["on_turn_end"](self)
        self._switch_player()
        if self.has_ended:
            self._hooks["on_game_end"](self)
        else:
            self._hooks["on_turn_start"](self)

    def _pay_for_combo(self, combo_index: int) -> None:
        """Perform coin transactions needed to obtain the specified combo.

        The current player:
        * Gets all coins that have been put on the specified combo.
        * Puts 1 coin on each combo above that (`combo_index` coins in total).

        If the player doesn't have enough coins, `RulesViolation` is raised.
        """
        coins_getting = self.combos[combo_index].coins
        if combo_index > self._current_player.coins + coins_getting:
            raise RulesViolation("Not enough coins, select a different race")
        self._current_player.coins += coins_getting - combo_index
        for combo in self.combos[:combo_index]:
            combo.coins += 1
        self.combos[combo_index].coins = 0

    def _pop_combo(self, index: int) -> None:
        """Remove the specified combo from the list of available combos.

        Then, append a new combo to the list.
        """
        chosen_race = self._races.pop(index)
        chosen_ability = self._abilities.pop(index)
        self._races.append(chosen_race)
        self._abilities.append(chosen_ability)
        self.combos.pop(index)
        next_combo = Combo(self._races[self._n_combos - 1],
                           self._abilities[self._n_combos - 1])
        self.combos.append(next_combo)

    def _switch_player(self) -> None:
        """Switch `_current_player` to the next player.

        Update `current_player_id` and `current_turn` accordingly.
        """
        self._current_player_id += 1
        if self.current_player_id == len(self.players):
            self._current_player_id = 0
            self._current_turn += 1
        self._current_player = self.players[self.current_player_id]
        self._current_player.acted_on_this_turn = False
        self._current_player.declined_on_this_turn = False