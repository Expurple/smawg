"""Backend engine for Small World board game.

See https://github.com/expurple/smawg for more info.
"""

import json
import random
from collections import defaultdict
from copy import deepcopy
from enum import Enum
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
    """A bunch of "dumb" mutable stats, related to the same player.

    Even though these stats are mutated during the game,
    they aren't supposed to be directly modified by library users.
    """

    def __init__(self, coins: int) -> None:
        """Initialize `Player` with an initial supply of `coins`."""
        self.active_race: Optional[Race] = None
        self.active_ability: Optional[Ability] = None
        self.decline_race: Optional[Race] = None
        self.decline_ability: Optional[Ability] = None
        self.active_regions = dict[int, int]()
        """Dict of controlled regions, in form of `{region: n_tokens}`."""
        self.decline_regions = set[int]()
        """A set of regions controlled by a single declined race token."""
        self.tokens_on_hand = 0
        self.coins = coins

    def _is_owning(self, region: int) -> bool:
        """Check if `Player` owns the given `region`."""
        return region in self.active_regions or region in self.decline_regions

    def _decline(self) -> None:
        """Put `Player`'s active race in decline state."""
        self.decline_regions = set(self.active_regions)
        self.active_regions.clear()
        self.tokens_on_hand = 0
        self.decline_race = self.active_race
        self.decline_ability = self.active_ability
        self.active_race = None
        self.active_ability = None

    def _pick_up_tokens(self) -> None:
        """Pick up available tokens, leaving 1 token in each owned region."""
        for region in self.active_regions:
            self.tokens_on_hand += self.active_regions[region] - 1
            self.active_regions[region] = 1

    def _set_active(self, combo: Combo) -> None:
        """Set `Race` and `Ability` from the given `combo` as active."""
        self.active_race = combo.race
        self.active_ability = combo.ability
        self.tokens_on_hand = combo.base_n_tokens


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

def _do_nothing(*args, **kwargs) -> None:
    """Just accept any arguments and do nothing."""
    pass


def _borders(borders_from_json: list[list[int]]) -> list[set[int]]:
    """Transform a list of region pairs into a list of sets for each region.

    Example:
    ```
    >>> _borders([[0, 1], [1, 2]])
    [
        {1},    # Neighbors of region 0
        {0, 2}, # Neighbors of region 1
        {1}     # Neighbors of region 2
    ]
    ```
    """
    # This assumes that every region is listed in `borders_from_json`.
    n_regions = max(max(pair) for pair in borders_from_json) + 1
    borders = [set[int]() for _ in range(n_regions)]
    for region1, region2 in borders_from_json:
        borders[region1].add(region2)
        borders[region2].add(region1)
    return borders


class RulesViolation(Exception):
    """Exception raised from `Game` methods when rules are violated."""

    pass


class GameEnded(RulesViolation):
    """Exception raised from `Game` methods when calling after the game end."""

    def __init__(self, *args) -> None:
        """Construct an exception with default `GameEnded` message."""
        msg = "The game is over, this action is not available anymore"
        super().__init__(msg, *args)


class _TurnStage(Enum):
    """The current stage of the player's turn.

    Determines, which actions (`Game` method calls) are allowed.
    """

    SELECT_COMBO = 0
    """Just started a turn without an active race and must pick a new one."""
    CAN_DECLINE = 1
    """Just started a turn with an existing active race and can decline."""
    DECLINED = 2
    """Just declined and must `end_turn()` now."""
    ACTIVE = 3
    """Selected/used an active race during the turn and can't decline now."""
    REDEPLOYMENT = 4
    """Done conquering, can only redeploy and end turn."""
    REDEPLOYMENT_TURN = 5
    """Pseudo-turn for redeploying tokens after attack from other player."""


def _check_rules(*, require_active: bool = False,
                 allow_during_redeployment: bool = True):
    """Add boilerplate rule checks to public `Game` methods.

    `require_active` specifies whether an action requires an active race.

    `allow_when_redeploying` specifies whether an action is allowed during the
    redeployment phase.
    """
    def decorator(game_method: Callable):
        @wraps(game_method)
        def wrapper(*args, **kwargs):
            # Perform necessary checks
            self: "Game" = args[0]
            if self.has_ended:
                raise GameEnded()
            if require_active and self.player.active_race is None:
                msg = "To do this, you need to control an active race"
                raise RulesViolation(msg)
            if not allow_during_redeployment and self._turn_stage in \
                    (_TurnStage.REDEPLOYMENT, _TurnStage.REDEPLOYMENT_TURN):
                msg = "This action is not allowed during redeployment"
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

    def __init__(self, assets: dict, *,
                 shuffle_data: bool = True,
                 dice_roll_func: Callable[[], int] = roll_dice,
                 hooks: Mapping[str, Callable] = dict()) -> None:
        """Initialize a game based on given `assets`.

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
        """
        jsonschema.validate(assets, ASSETS_SCHEMA, resolver=_JS_REF_RESOLVER)
        assets = shuffle(assets) if shuffle_data else deepcopy(assets)
        n_coins: int = assets["n_coins_on_start"]
        n_players: int = assets["n_players"]
        self._regions: list[dict] = assets["map"]["tiles"]
        self._borders = _borders(assets["map"]["tile_borders"])
        self._abilities = [Ability(a) for a in assets["abilities"]]
        self._races = [Race(r) for r in assets["races"]]
        self._n_combos: int = assets["n_selectable_combos"]
        self._n_turns: int = assets["n_turns"]
        self._current_turn: int = 1
        visible_ra = islice(zip(self._races, self._abilities), self._n_combos)
        self._combos = [Combo(r, a) for r, a in visible_ra]
        self._players = [Player(n_coins) for _ in range(n_players)]
        self._player_id = 0
        self._next_player_id = self._increment(self._player_id)
        """Helper to preserve `_current_player_id` during redeployment."""
        self._roll_dice = dice_roll_func
        self._turn_stage = _TurnStage.SELECT_COMBO
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
    def player_id(self) -> int:
        """0-based index of the current active player in `players`."""
        return self._player_id

    @property
    def player(self) -> Player:
        """The current active `Player`."""
        return self.players[self.player_id]

    @_check_rules(require_active=True, allow_during_redeployment=False)
    def decline(self) -> None:
        """Put player's active race in decline state.

        Exceptions raised:
        * `RulesViolation`:
            * If the player is already in decline.
            * If the player has already used his active race during this turn.
            * If this method is called during the redeployment phase.
        * `GameEnded` - if this method is called after the game has ended.
        """
        if self._turn_stage in (_TurnStage.SELECT_COMBO, _TurnStage.DECLINED):
            raise RulesViolation("You're already in Decline")
        if self._turn_stage == _TurnStage.ACTIVE:
            msg = "You've already used your active race during this turn. " \
                  "You can only decline during the next turn"
            raise RulesViolation(msg)
        self.player._decline()
        self._turn_stage = _TurnStage.DECLINED

    @_check_rules(allow_during_redeployment=False)
    def select_combo(self, combo_index: int) -> None:
        """Select the combo at specified `combo_index` as active.

        During that:
        * The player gets all coins that have been put on that combo.
        * Puts 1 coin on each combo above that (`combo_index` coins in total).
        * Then, the next combo is revealed.

        Exceptions raised:
        * `ValueError` - if not `0 <= combo_index < len(combos)`.
        * `RulesViolation`:
            * If the player already has an active race.
            * If the player has just declined during this turn.
            * If the player doesn't have enough coins.
        * `GameEnded` - if this method is called after the game has ended.
        """
        if not 0 <= combo_index < len(self.combos):
            msg = f"combo_index must be between 0 and {len(self.combos)}"
            raise ValueError(msg)
        if self._turn_stage == _TurnStage.DECLINED:
            raise RulesViolation("You need to finish your turn now and select "
                                 "a new race during the next turn")
        if self._turn_stage != _TurnStage.SELECT_COMBO:
            raise RulesViolation("You need to decline first")
        self._pay_for_combo(combo_index)
        self.player._set_active(self.combos[combo_index])
        self._pop_combo(combo_index)
        self._turn_stage = _TurnStage.ACTIVE

    @_check_rules(require_active=True, allow_during_redeployment=False)
    def conquer(self, region: int) -> None:
        """Conquer the given map `region`.

        Exceptions raised:
        * `ValueError` - if not `0 <= region < len(assets["map"]["tiles"])`.
        * `RulesViolation` - if the player attempts to:
            * Do the first conquest of a new race not at the map border.
            * Conquer a region that isn't adjacent to any owned regions.
            * Conquer a region occupied by their own active race.
            * Conquer without having enough tokens at hand.
            * Or if this method is called during the redeployment phase.
        * `GameEnded` - if this method is called after the game has ended.
        """
        if not 0 <= region < len(self._regions):
            msg = f"region must be between 0 and {len(self._regions)}"
            raise ValueError(msg)
        if len(self.player.active_regions) == 0 \
                and not self._regions[region]["is_at_map_border"]:
            msg = "The initial conquest must be at the map border"
            raise RulesViolation(msg)
        if region in self.player.active_regions:
            raise RulesViolation("Can't conquer your own region")
        has_adjacent = any(region in self._borders[own]
                           for own in self.player.active_regions)
        if len(self.player.active_regions) > 0 and not has_adjacent:
            msg = "The region must be adjacent to any of your active regions"
            raise RulesViolation(msg)
        tokens_required = self._get_conquest_cost(region)
        tokens_on_hand = self.player.tokens_on_hand
        if tokens_on_hand < tokens_required:
            msg = f"Not enough tokens on hand (you have {tokens_on_hand}, " \
                  f"but need {tokens_required})"
            raise RulesViolation(msg)
        self._kick_out_owner(region)
        self.player.tokens_on_hand -= tokens_required
        self.player.active_regions[region] = tokens_required
        self._turn_stage = _TurnStage.ACTIVE

    @_check_rules(require_active=True, allow_during_redeployment=False)
    def start_redeployment(self) -> None:
        """Pick up tokens to redeploy, leaving 1 token in each owned region.

        This action ends conquests. After this method is called,
        the player should deploy tokens from hand and then end the turn.

        Exceptions raised:
        * `RulesViolation`:
            * If the player doesn't control any region with his active race.
            * If this method is called during the redeployment phase.
        * `GameEnded` - if this method is called after the game has ended.
        """
        if not self.player.active_regions:
            raise RulesViolation("You must control at least one active region")
        self.player._pick_up_tokens()
        self._turn_stage = _TurnStage.REDEPLOYMENT

    @_check_rules(require_active=True)
    def deploy(self, n_tokens: int, region: int) -> None:
        """Deploy `n_tokens` from hand to the specified own `region`.

        Exceptions raised:
        * `ValueError`:
            * if `n_tokens < 1`
            * if not `0 <= region < len(assets["map"]["tiles"])`.
        * `RulesViolation` - if the player:
            * Doesn't control the specified `region` with his active race.
            * Doesn't have `n_tokens` on hand.
        * `GameEnded` - if this method is called after the game has ended.
        """
        if n_tokens < 1:
            raise ValueError("n_tokens must be greater then 0")
        if not 0 <= region < len(self._regions):
            msg = f"region must be between 0 and {len(self._regions)}"
            raise ValueError(msg)
        if region not in self.player.active_regions:
            raise RulesViolation("Can only deploy to owned region")
        tokens_on_hand = self.player.tokens_on_hand
        if n_tokens > tokens_on_hand:
            msg = f"Not enough tokens on hand (you have {tokens_on_hand})"
            raise RulesViolation(msg)
        self.player.tokens_on_hand -= n_tokens
        self.player.active_regions[region] += n_tokens
        if self._turn_stage == _TurnStage.CAN_DECLINE:
            self._turn_stage = _TurnStage.ACTIVE

    @_check_rules()
    def end_turn(self) -> None:
        """End turn (full or redeployment) and give control to the next player.

        Automatically calculate+pay coin rewards and fire appropriate hooks.

        Exceptions raised:
        * `RulesViolation` - if the player:
            * Must select a new combo and haven't done that yet.
            * Must deploy tokens from hand and haven't done that yet.
        * `GameEnded` - if this method is called after the game has ended.
        """
        if self._turn_stage == _TurnStage.SELECT_COMBO:
            raise RulesViolation("You need to select a new race+ability combo "
                                 "before ending this turn")
        tokens_on_hand = self.player.tokens_on_hand
        if tokens_on_hand > 0:
            msg = f"You need to use remaining {tokens_on_hand} tokens on hand"
            if self._turn_stage == _TurnStage.CAN_DECLINE:
                msg += " or decline"
            raise RulesViolation(msg)
        if self._turn_stage != _TurnStage.REDEPLOYMENT_TURN:
            self._reward_coins_for_turn()
            self._hooks["on_turn_end"](self)
        self._switch_player()

    def _pay_for_combo(self, combo_index: int) -> None:
        """Perform coin transactions needed to obtain the specified combo.

        The current player:
        * Gets all coins that have been put on the specified combo.
        * Puts 1 coin on each combo above that (`combo_index` coins in total).

        If the player doesn't have enough coins, `RulesViolation` is raised.
        """
        coins_getting = self.combos[combo_index].coins
        if combo_index > self.player.coins + coins_getting:
            raise RulesViolation("Not enough coins, select a different race")
        self.player.coins += coins_getting - combo_index
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

    def _owner(self, region: int) -> Optional[int]:
        """Return the owner of the given `region` or `None` if there's none."""
        for i, p in enumerate(self.players):
            if p._is_owning(region):
                return i
        return None

    def _get_conquest_cost(self, region: int) -> int:
        """Return the amount of tokens needed to conquer the given `region`."""
        cost = 3
        owner_idx = self._owner(region)
        if owner_idx is not None:
            owner = self.players[owner_idx]
            cost += owner.active_regions.get(region, 1)  # 1 if declined
        return cost

    def _kick_out_owner(self, region: int) -> None:
        """Move tokens from `region` to the storage tray and owner's hand.

        If the `region` has no owner, do nothing.
        """
        owner_idx = self._owner(region)
        if owner_idx is None:
            return
        owner = self.players[owner_idx]
        if region in owner.active_regions:
            n_tokens = owner.active_regions[region]
            del owner.active_regions[region]
            owner.tokens_on_hand += n_tokens - 1
        else:
            owner.decline_regions.remove(region)

    def _reward_coins_for_turn(self) -> None:
        """Calculate and pay victory coins for the passed turn."""
        self.player.coins += len(self.player.active_regions)
        self.player.coins += len(self.player.decline_regions)

    def _switch_player(self) -> None:
        """Switch to the next player, updating state and firing hooks."""
        # This part switches to redeployment "pseudo-turn" if needed:
        for i, p in enumerate(self.players):
            need_redeploy = p.tokens_on_hand > 0 and len(p.active_regions) > 0
            if need_redeploy and i != self._next_player_id:
                self._player_id = i
                self._turn_stage = _TurnStage.REDEPLOYMENT_TURN
                self._hooks["on_redeploy"](self)
                return
        # This part performs the actual switch to the next turn:
        self._player_id = self._next_player_id
        self._next_player_id = self._increment(self._player_id)
        if self._player_id == 0:
            self._current_turn += 1
        if self.player.active_race is None:
            self._turn_stage = _TurnStage.SELECT_COMBO
        else:
            self._turn_stage = _TurnStage.CAN_DECLINE
        if self.has_ended:
            self._hooks["on_game_end"](self)
        else:
            self.player._pick_up_tokens()
            self._hooks["on_turn_start"](self)

    def _increment(self, player_id: int) -> int:
        """Increment the given `player_id`, wrapping around if needed."""
        return (player_id + 1) % len(self.players)
