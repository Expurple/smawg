"""Backend engine for Small World board game.

See https://github.com/expurple/smawg for more info about the project.
"""

import json
import random
from collections import defaultdict, deque
from dataclasses import dataclass
from enum import auto, Enum
from itertools import islice
from typing import Any, Callable, cast, Optional, TypedDict

import jsonschema

import smawg.exceptions as exc
from smawg._metadata import SCHEMA_DIR


__all__ = [
    "Ability", "Combo", "Game", "Hooks", "Player", "Race", "Region", "validate"
]


# --------------------------- assets validation -------------------------------

with open(f"{SCHEMA_DIR}/assets.json") as file:
    _ASSETS_SCHEMA: dict[str, Any] = json.load(file)

_STRICT_ASSETS_SCHEMA = {**_ASSETS_SCHEMA, "additionalProperties": False}

_LOCAL_REF_RESOLVER = jsonschema.RefResolver(f"file://{SCHEMA_DIR}/", {})
"""Fixes references to local schemas."""


def validate(assets: dict[str, Any], *, strict: bool = False) -> None:
    """Validate the game assets.

    Raise `jsonschema.exceptions.ValidationError`
    if `assets` don't match the schema in `assets_schema/`.

    If `strict=True`, also fail on undocumented keys.

    Raise `smawg.exceptions.InvalidAssets` if
    - there are less than `2 * n_players + n_selectable_combos` races; or
    - there are less than `n_players + n_selectable_combos` abilities; or
    - tile borders reference non-existing tiles.
    """
    schema = _STRICT_ASSETS_SCHEMA if strict else _ASSETS_SCHEMA
    jsonschema.validate(assets, schema, resolver=_LOCAL_REF_RESOLVER)
    _validate_n_races(assets)
    _validate_n_abilities(assets)
    _validate_tile_indexes(assets)


def _validate_n_races(assets: dict[str, Any]) -> None:
    """Assume that `assets` are already validated against the JSON schema."""
    n_races = len(assets["races"])
    n_players = assets["n_players"]
    n_selectable_combos = assets["n_selectable_combos"]
    safe_n_races = 2 * n_players + n_selectable_combos
    if n_races < safe_n_races:
        raise exc.InvalidAssets(
            f"{n_races} races are not enough to always guarantee "
            f"{n_selectable_combos} selectable combos "
            f"for {n_players} players, need at least {safe_n_races} races"
        )


def _validate_n_abilities(assets: dict[str, Any]) -> None:
    """Assume that `assets` are already validated against the JSON schema."""
    n_abilities = len(assets["abilities"])
    n_players = assets["n_players"]
    n_selectable_combos = assets["n_selectable_combos"]
    safe_n_abilities = n_players + n_selectable_combos
    if n_abilities < safe_n_abilities:
        raise exc.InvalidAssets(
            f"{n_abilities} abilities are not enough to always guarantee "
            f"{n_selectable_combos} selectable combos for "
            f"{n_players} players, need at least {safe_n_abilities} abilities"
        )


def _validate_tile_indexes(assets: dict[str, Any]) -> None:
    """Assume that `assets` are already validated against the JSON schema."""
    n_tiles = len(assets["map"]["tiles"])
    for t1, t2 in assets["map"]["tile_borders"]:
        greater_index = max(t1, t2)
        if greater_index >= n_tiles:
            raise exc.InvalidAssets(
                f"Tile border [{t1}, {t2}] references a non-existing tile: "
                f"{greater_index} (the map only has {n_tiles} tiles)"
            )


# -------------------------- "dumb" data objects ------------------------------

@dataclass
class Region:
    """Info about a region from the game map.

    `is_at_map_border` and `terrain` are immutable.

    `has_a_lost_tribe` is mutable -
    it becomes `False` after the region is conquered.
    """

    has_a_lost_tribe: bool
    is_at_map_border: bool
    terrain: str


@dataclass(frozen=True)
class Ability:
    """Immutable description of an ability (just like on a physical banner)."""

    name: str
    n_tokens: int


@dataclass(frozen=True)
class Race:
    """Immutable description of a race (just like on a physical banner)."""

    name: str
    n_tokens: int
    max_n_tokens: int


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
        self.active_ability: Optional[Ability] = None
        self.active_race: Optional[Race] = None
        self.decline_race: Optional[Race] = None
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

def _shuffle(assets: dict[str, Any]) -> dict[str, Any]:
    """Shuffle the order of `Race` and `Ability` banners in `assets`.

    Just like you would do in a physical Small World game.

    Returns a copy as shallow as possible:

    ```python
    # New root assets dict
    {
        "races":       [...],  # New list with references to the same objects
        "abilities":   [...],  # New list with references to the same objects
        "other fields": ...    # References to the same objects
    }
    ```
    """
    assets = {
        **assets,
        "races": list(assets["races"]),
        "abilities": list(assets["abilities"])
    }
    random.shuffle(assets["races"])
    random.shuffle(assets["abilities"])
    return assets


def _roll_dice() -> int:
    """Return a random dice roll result."""
    return random.choice((0, 0, 0, 1, 2, 3))


# --------------------- the Small World engine itself -------------------------

def _do_nothing(*args: Any, **kwargs: Any) -> None:
    """Just accept any arguments and do nothing."""
    pass


def _borders(tile_borders: list[list[int]], n_tiles: int) -> list[set[int]]:
    """Transform a list of region pairs into a list of sets for each region.

    Assume that `tile_borders` and `n_tiles`
    are already validated by the caller.

    Example:
    ```
    >>> _borders([[0, 1], [1, 2]], 4)
    [
        {1},    # Neighbors of region 0
        {0, 2}, # Neighbors of region 1
        {1},    # Neighbors of region 2
        {}      # Neighbors of region 3
    ]
    ```
    """
    borders = [set[int]() for _ in range(n_tiles)]
    for region1, region2 in tile_borders:
        borders[region1].add(region2)
        borders[region2].add(region1)
    return borders


class _TurnStage(Enum):
    """The current stage of the player's turn.

    Determines, which actions (`Game` method calls) are allowed.
    """

    SELECT_COMBO = auto()
    """Just started a turn without an active race and must pick a new one."""
    CAN_DECLINE = auto()
    """Just started a turn with an existing active race and can decline."""
    DECLINED = auto()
    """Just declined and must `end_turn()` now."""
    ACTIVE = auto()
    """Selected/used an active race during the turn and can't decline now."""
    CONQUESTS = auto()
    """Started conquering regions and can't abandon regions now."""
    USED_DICE = auto()
    """Done conquering, can only (re)deploy tokens and end turn."""
    REDEPLOYMENT = auto()
    """Can only deploy remaining tokens from hand and end turn."""
    REDEPLOYMENT_TURN = auto()
    """Pseudo-turn for redeploying tokens after attack from other player."""


class _GameState:
    """An interface for accessing the `Game` state."""

    def __init__(self, assets: dict[str, Any]) -> None:
        """Initialize the game state from `assets`.

        Assume thet `assets` are already validated by the caller.
        """
        n_coins: int = assets["n_coins_on_start"]
        n_players: int = assets["n_players"]
        self._regions = [Region(**t) for t in assets["map"]["tiles"]]
        self._borders = _borders(assets["map"]["tile_borders"],
                                 len(self._regions))
        self._n_combos: int = assets["n_selectable_combos"]
        self._n_turns: int = assets["n_turns"]
        self._current_turn: int = 1
        abilities = (Ability(**a) for a in assets["abilities"])
        races = (Race(**r) for r in assets["races"])
        visible_ra = islice(zip(races, abilities), self._n_combos)
        self._combos = [Combo(r, a) for r, a in visible_ra]
        self._invisible_abilities = deque(abilities)
        self._invisible_races = deque(races)
        self._players = [Player(n_coins) for _ in range(n_players)]
        self._player_id = 0
        self._turn_stage = _TurnStage.SELECT_COMBO

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
    def regions(self) -> list[Region]:
        """Info about regions on the map."""
        return self._regions

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

    def _owner(self, region: int) -> Optional[int]:
        """Return the owner of the given `region` or `None` if there's none."""
        for i, p in enumerate(self.players):
            if p._is_owning(region):
                return i
        return None


class _Rules:
    """Implements the game rules."""

    def __init__(self, game: _GameState) -> None:
        self.game = game

    def check_decline(self) -> None:
        self._assert_game_has_not_ended()
        self._assert_has_active_race()
        self._assert_not_in_redeployment()
        if self.game._turn_stage in (
                _TurnStage.ACTIVE, _TurnStage.CONQUESTS, _TurnStage.USED_DICE):
            raise exc.DecliningWhenActive()

    def check_combo(self, combo_index: int) -> None:
        """Assume that `combo_index` is in valid range."""
        self._assert_game_has_not_ended()
        self._assert_not_in_redeployment()
        if self.game._turn_stage == _TurnStage.DECLINED:
            raise exc.SelectingOnDeclineTurn()
        if self.game._turn_stage != _TurnStage.SELECT_COMBO:
            raise exc.SelectingWhenActive()
        coins_getting = self.game.combos[combo_index].coins
        if combo_index > self.game.player.coins + coins_getting:
            raise exc.NotEnoughCoins()

    def check_abandon(self, region: int) -> None:
        """Assume that `region` is in valid range."""
        self._assert_game_has_not_ended()
        self._assert_has_active_race()
        self._assert_not_in_redeployment()
        if region not in self.game.player.active_regions:
            raise exc.NonControlledRegion()
        if self.game._turn_stage in (_TurnStage.CONQUESTS,
                                     _TurnStage.USED_DICE):
            raise exc.AbandoningAfterConquests()

    def check_conquer(self, region: int, *, use_dice: bool) -> None:
        """Assume that `region` is in valid range."""
        if use_dice:
            self._check_conquer_with_dice(region)
        else:
            self._check_conquer_without_dice(region)

    def check_start_redeployment(self) -> None:
        self._assert_game_has_not_ended()
        self._assert_has_active_race()
        self._assert_not_in_redeployment()
        if not self.game.player.active_regions:
            raise exc.NoActiveRegions()

    def check_deploy(self, n_tokens: int, region: int) -> None:
        """Assume positive `n_tokens` and that `region` is in valid range."""
        self._assert_game_has_not_ended()
        self._assert_has_active_race()
        if region not in self.game.player.active_regions:
            raise exc.NonControlledRegion()
        tokens_on_hand = self.game.player.tokens_on_hand
        if n_tokens > tokens_on_hand:
            raise exc.NotEnoughTokensToDeploy(tokens_on_hand)

    def check_end_turn(self) -> None:
        self._assert_game_has_not_ended()
        if self.game._turn_stage == _TurnStage.SELECT_COMBO:
            raise exc.EndBeforeSelect()
        tokens_on_hand = self.game.player.tokens_on_hand
        if tokens_on_hand > 0:
            if self.game._turn_stage == _TurnStage.USED_DICE \
                    and len(self.game.player.active_regions) == 0:
                # The player has no regions and no ability to conquer, so
                # he can't possibly deploy his tokens. Don't raise the error.
                pass
            else:
                cd = self.game._turn_stage == _TurnStage.CAN_DECLINE
                raise exc.UndeployedTokens(tokens_on_hand, can_decline=cd)

    def conquest_cost(self, region: int) -> int:
        """Return the amount of tokens needed to conquer the given `region`.

        Assumes that `region` is a valid conquest target.
        If it's not, the return value is undefined.
        """
        cost = 3
        owner_idx = self.game._owner(region)
        if owner_idx is not None:
            owner = self.game.players[owner_idx]
            cost += owner.active_regions.get(region, 1)  # 1 if declined
        elif self.game.regions[region].has_a_lost_tribe:
            cost += 1
        return cost

    def calculate_turn_reward(self) -> int:
        """Calculate the amount of coins to be paid for the passed turn."""
        player = self.game.player
        return len(player.active_regions) + len(player.decline_regions)

    def _check_conquer_with_dice(self, region: int) -> None:
        self._check_conquer_common(region)
        tokens_on_hand = self.game.player.tokens_on_hand
        if tokens_on_hand < 1:
            raise exc.RollingWithoutTokens()
        minimum_required = self.conquest_cost(region) - 3
        if tokens_on_hand < minimum_required:
            raise exc.NotEnoughTokensToRoll(tokens_on_hand, minimum_required)

    def _check_conquer_without_dice(self, region: int) -> None:
        self._check_conquer_common(region)
        tokens_on_hand = self.game.player.tokens_on_hand
        tokens_required = self.conquest_cost(region)
        if tokens_on_hand < tokens_required:
            raise exc.NotEnoughTokensToConquer(tokens_on_hand, tokens_required)

    def _check_conquer_common(self, region: int) -> None:
        """Common checks for all conquests (with or without dice)."""
        self._assert_game_has_not_ended()
        self._assert_has_active_race()
        self._assert_not_in_redeployment()
        if self.game._turn_stage == _TurnStage.USED_DICE:
            raise exc.AlreadyUsedDice()
        if len(self.game.player.active_regions) == 0 \
                and not self.game.regions[region].is_at_map_border:
            raise exc.NotAtBorder()
        if region in self.game.player.active_regions:
            raise exc.ConqueringOwnRegion()
        has_adjacent = any(region in self.game._borders[own]
                           for own in self.game.player.active_regions)
        if len(self.game.player.active_regions) > 0 and not has_adjacent:
            raise exc.NonAdjacentRegion()

    def _assert_game_has_not_ended(self) -> None:
        if self.game.has_ended:
            raise exc.GameEnded()

    def _assert_has_active_race(self) -> None:
        if self.game.player.active_race is None:
            raise exc.NoActiveRace()

    def _assert_not_in_redeployment(self) -> None:
        if self.game._turn_stage in \
                (_TurnStage.REDEPLOYMENT, _TurnStage.REDEPLOYMENT_TURN):
            raise exc.ForbiddenDuringRedeployment()


class Hooks(TypedDict, total=False):
    """`TypedDict` annotation for `Game` hooks."""

    on_turn_start: Callable[["Game"], None]
    on_dice_rolled: Callable[["Game", int, bool], None]
    on_turn_end: Callable[["Game"], None]
    on_redeploy: Callable[["Game"], None]
    on_game_end: Callable[["Game"], None]


class Game(_GameState):
    """High-level representation of a single Small World game.

    Provides:
    * Flexible configuration on construction (see `__init__`).
    * API for performing in-game actions (as methods).
    * Access to the game state (as readonly properties).

    Method calls automatically update `Game` state according to the rules,
    or raise exceptions if the call violates the rules.
    """

    # Under the hood, rules are implemented in `_Rules`
    # and properties are implemented in the base class.
    # This class only implements game actions and hooks.

    def __init__(self, assets: dict[str, Any], *,
                 shuffle_data: bool = True,
                 dice_roll_func: Callable[[], int] = _roll_dice,
                 hooks: Hooks = {}) -> None:
        """Initialize a game based on given `assets`.

        `assets` are validated using `validate()`, all errors are propagated.

        When initialization is finished, the object is ready to be used by
        player 0. `"on_turn_start"` hook is fired immediately, if provided.

        Provide `shuffle_data=False` to preserve
        the known order of races and ablities in `assets`.

        Provide custom `dice_roll_func` to get pre-determined
        (or even dynamically controlled) dice roll results.

        Provide optional `hooks` to automatically fire on certain events.
        For details, see `docs/hooks.md`.
        """
        validate(assets)
        if shuffle_data:
            assets = _shuffle(assets)
        super().__init__(assets)
        self._next_player_id = self._increment(self.player_id)
        """Helper to preserve `_current_player_id` during redeployment."""
        self._roll_dice = dice_roll_func
        self._hooks = cast(Hooks, defaultdict(lambda: _do_nothing, **hooks))
        # Only after all other fields have been initialized.
        self._rules = _Rules(self)
        # Only after `self` has been fully initialized.
        self._hooks["on_turn_start"](self)

    def decline(self) -> None:
        """Put player's active race in decline state.

        Exceptions raised:
        * `smawg.exceptions.NoActiveRace`
            if the player is already in decline.
        * `smawg.exceptions.DecliningWhenActive`
            if the player has already used his active race during this turn.
        * `smawg.exceptions.ForbiddenDuringRedeployment`
            if this method is called during the redeployment phase.
        * `smawg.exceptions.GameEnded`
            if this method is called after the game has ended.
        """
        self._rules.check_decline()

        # Mark the current ability and decline race as available for reuse.
        ability = self.player.active_ability
        assert ability is not None, "Always true, this is just type narrowing."
        self._invisible_abilities.append(ability)
        if self.player.decline_race is not None:
            self._invisible_races.append(self.player.decline_race)

        self.player._decline()
        self._turn_stage = _TurnStage.DECLINED

    def select_combo(self, combo_index: int) -> None:
        """Select the combo at specified `combo_index` as active.

        During that:
        * The player gets all coins that have been put on that combo.
        * Puts 1 coin on each combo above that (`combo_index` coins in total).
        * Then, the next combo is revealed.

        Exceptions raised:
        * `ValueError`
            if `combo_index not in range(len(self.combos))`.
        * `smawg.exceptions.SelectingWhenActive`
            if the player already has an active race.
        * `smawg.exceptions.SelectingOnDeclineTurn`
            if the player has just declined during this turn.
        * `smawg.exceptions.NotEnoughCoins`
            if the player doesn't have enough coins.
        * `smawg.exceptions.ForbiddenDuringRedeployment`
            if this method is called during the redeployment phase.
        * `smawg.exceptions.GameEnded`
            if this method is called after the game has ended.
        """
        if combo_index not in range(len(self.combos)):
            msg = f"combo_index must be between 0 and {len(self.combos)}"
            raise ValueError(msg)
        self._rules.check_combo(combo_index)
        self._pay_for_combo(combo_index)
        chosen_combo = self.combos.pop(combo_index)
        self.player._set_active(chosen_combo)
        self._turn_stage = _TurnStage.ACTIVE
        # Reveal the next combo
        next_race = self._invisible_races.popleft()
        next_ability = self._invisible_abilities.popleft()
        self.combos.append(Combo(next_race, next_ability))

    def abandon(self, region: int) -> None:
        """Abandon the given map `region`.

        Exceptions raised:
        * `ValueError`
            if `region not in range(len(self.regions))`.
        * `smawg.exceptions.NoActiveRace`
            if the player doesn't have an active race.
        * `smawg.exceptions.NonControlledRegion`
            if player doesn't control the `region` with his active race.
        * `smawg.exceptions.AbandoningAfterConquests`
            if the player has made conquests during this turn.
        * `smawg.exceptions.ForbiddenDuringRedeployment`
            if this method is called during the redeployment phase.
        * `smawg.exceptions.GameEnded`
            if this method is called after the game has ended.
        """
        if region not in range(len(self.regions)):
            msg = f"region must be between 0 and {len(self.regions)}"
            raise ValueError(msg)
        self._rules.check_abandon(region)
        self.player.tokens_on_hand += self.player.active_regions.pop(region)
        self._turn_stage = _TurnStage.ACTIVE

    def conquer(self, region: int, *, use_dice: bool = False) -> None:
        """Conquer the given map `region`.

        When `use_dice=True` is given, attempt to use reinforcements.

        Exceptions raised:
        * `ValueError`
            if `region not in range(len(self.regions))`.
        * `smawg.exceptions.NoActiveRace`
            if the player doesn't have an active race.
        * `smawg.exceptions.NotAtBorder`
            if the first conquest of a new race is not at the map border.
        * `smawg.exceptions.NonAdjacentRegion`
            if `region` isn't adjacent to any owned regions.
        * `smawg.exceptions.ConqueringOwnRegion`
            if `region` is occupied by player's own active race.
        * `smawg.exceptions.NotEnoughTokensToConquer`
            if conquering without dice and without enough tokens on hand.
        * `smawg.exceptions.RollingWithoutTokens`
            if conquering with dice while having 0 tokens on hand.
        * `smawg.exceptions.NotEnoughTokensToRoll`
            if conquering with dice, while needing >3 additional tokens.
        * `smawg.exceptions.NotEnoughTokensToRoll`
            if conquering again after rolling the reinforcements dice.
        * `smawg.exceptions.ForbiddenDuringRedeployment`
            if this method is called during the redeployment phase.
        * `smawg.exceptions.GameEnded`
            if this method is called after the game has ended.
        """
        if region not in range(len(self.regions)):
            msg = f"region must be between 0 and {len(self.regions)}"
            raise ValueError(msg)
        self._rules.check_conquer(region, use_dice=use_dice)
        if use_dice:
            self._conquer_with_dice(region)
        else:
            self._conquer_without_dice(region)

    def start_redeployment(self) -> None:
        """Pick up tokens to redeploy, leaving 1 token in each owned region.

        This action ends conquests. After this method is called,
        the player should deploy tokens from hand and then end the turn.

        Exceptions raised:
        * `smawg.exceptions.NoActiveRace`
            if the player doesn't have an active race.
        * `smawg.exceptions.NoActiveRegions`
            if the player doesn't control any regions with his active race.
        * `smawg.exceptions.ForbiddenDuringRedeployment`
            if this method is called during the redeployment phase.
        * `smawg.exceptions.GameEnded`
            if this method is called after the game has ended.
        """
        self._rules.check_start_redeployment()
        self.player._pick_up_tokens()
        self._turn_stage = _TurnStage.REDEPLOYMENT

    def deploy(self, n_tokens: int, region: int) -> None:
        """Deploy `n_tokens` from hand to the specified own `region`.

        Exceptions raised:
        * `ValueError`
            if `n_tokens < 1` or
            if `region not in range(len(self.regions))`.
        * `smawg.exceptions.NoActiveRace`
            if the player doesn't have an active race.
        * `smawg.exceptions.NonControlledRegion`
            if the player doesn't control the `region` with his active race.
        * `smawg.exceptions.NotEnoughTokensToDeploy`
            if the player doesn't have `n_tokens` on hand.
        * `smawg.exceptions.GameEnded`
            if this method is called after the game has ended.
        """
        if n_tokens < 1:
            raise ValueError("n_tokens must be greater then 0")
        if region not in range(len(self.regions)):
            msg = f"region must be between 0 and {len(self.regions)}"
            raise ValueError(msg)
        self._rules.check_deploy(n_tokens, region)
        self.player.tokens_on_hand -= n_tokens
        self.player.active_regions[region] += n_tokens
        if self._turn_stage == _TurnStage.CAN_DECLINE:
            self._turn_stage = _TurnStage.ACTIVE

    def end_turn(self) -> None:
        """End turn (full or redeployment) and give control to the next player.

        Automatically calculate+pay coin rewards and fire appropriate hooks.

        Exceptions raised:
        * `smawg.exceptions.EndBeforeSelect`
            if the player must select a new combo and haven't done that yet.
        * `smawg.exceptions.UndeployedTokens`
            if player must deploy tokens from hand and haven't done that yet.
        * `smawg.exceptions.GameEnded`
            if this method is called after the game has ended.
        """
        self._rules.check_end_turn()
        if self._turn_stage != _TurnStage.REDEPLOYMENT_TURN:
            self.player.coins += self._rules.calculate_turn_reward()
            self._hooks["on_turn_end"](self)
        self._switch_player()

    def _pay_for_combo(self, combo_index: int) -> None:
        """Perform coin transactions needed to obtain the specified combo.

        The current player:
        * Gets all coins that have been put on the specified combo.
        * Puts 1 coin on each combo above that (`combo_index` coins in total).

        The rules are expected to be already checked in `select_combo()`.
        """
        coins_getting = self.combos[combo_index].coins
        self.player.coins += coins_getting - combo_index
        for combo in self.combos[:combo_index]:
            combo.coins += 1
        self.combos[combo_index].coins = 0

    def _conquer_without_dice(self, region: int) -> None:
        """Implementation of `conquer()` with `use_dice=False`.

        The rules are expected to be already checked in `conquer()`.
        """
        tokens_required = self._rules.conquest_cost(region)
        self._kick_out_owner(region)
        self.player.tokens_on_hand -= tokens_required
        self.player.active_regions[region] = tokens_required
        self._turn_stage = _TurnStage.CONQUESTS

    def _conquer_with_dice(self, region: int) -> None:
        """Implementation of `conquer()` with `use_dice=True`.

        The rules are expected to be already checked in `conquer()`.
        """
        tokens_required = self._rules.conquest_cost(region)
        tokens_on_hand = self.player.tokens_on_hand
        dice_value = self._roll_dice()
        is_success = tokens_on_hand + dice_value >= tokens_required
        if is_success:
            own_tokens_used = max(tokens_required - dice_value, 1)
            self._kick_out_owner(region)
            self.player.tokens_on_hand -= own_tokens_used
            self.player.active_regions[region] = own_tokens_used
        self._turn_stage = _TurnStage.USED_DICE
        self._hooks["on_dice_rolled"](self, dice_value, is_success)

    def _kick_out_owner(self, region: int) -> None:
        """Move tokens from `region` to the storage tray and owner's hand.

        If the `region` has no owner, do nothing.
        """
        self.regions[region].has_a_lost_tribe = False
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
        self._next_player_id = self._increment(self.player_id)
        if self.player_id == 0:
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
