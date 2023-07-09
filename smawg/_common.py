"""Common types used both by rules plugins and `Game`.

Having this separate file is necessary
to avoid circular imports in bundled rule plugins.

See https://github.com/expurple/smawg for more info about the project.
"""

from abc import ABC, abstractmethod
from collections import deque
from copy import deepcopy
from enum import auto, Enum
from itertools import islice
from typing import Iterator

from pydantic import NonNegativeInt, PositiveInt, model_validator
from pydantic.dataclasses import dataclass


# When modifying this, don't forget to modify `smawg.__all__`.
__all__ = [
    "Region", "Ability", "Race", "Map", "Assets", "Combo", "Player",
    "_TurnStage", "GameState", "RulesViolation", "AbstractRules"
]


# ---------------- Game assets, usually loaded from a JSON file ---------------

@dataclass
class Region:
    """Info about a region from the game map.

    `is_at_map_border` and `terrain` are immutable.

    `has_a_lost_tribe` is mutable -
    it becomes `False` after the region is conquered.
    """

    terrain: str
    has_a_lost_tribe: bool
    is_at_map_border: bool = False
    """The type of terrain (Forest, Mountain, etc)"""


@dataclass(frozen=True)
class Ability:
    """Immutable description of an ability (just like on a physical banner)."""

    name: str
    n_tokens: NonNegativeInt
    "The number of additional race tokens the player gets."


@dataclass(frozen=True)
class Race:
    """Immutable description of a race (just like on a physical banner)."""

    name: str
    n_tokens: PositiveInt
    """The base number of tokens the player gets, regardless of the ability."""
    max_n_tokens: PositiveInt
    """The total number of race tokens in the storage."""


@dataclass(frozen=True)
class Map:
    """Machine-readable, graph-like representation of the game map.

    If the map is invalid, constructor raises `pydantic.ValidationError`.
    """

    tiles: list[Region]
    """A list of map tiles (nodes in the graph)."""
    tile_borders: list[tuple[NonNegativeInt, NonNegativeInt]]
    """A list of borders between adjacent tiles (edges in the graph)."""

    @model_validator(mode="after")  # type:ignore  # idk why it complains
    def _validate_tile_indexes(self) -> "Map":
        n_tiles = len(self.tiles)
        for t1, t2 in self.tile_borders:
            greater_index = max(t1, t2)
            if greater_index >= n_tiles:
                raise ValueError(
                    f"tile border ({t1}, {t2}) references a non-existing tile:"
                    f" {greater_index} (the map has {n_tiles} tiles)"
                )
        return self


@dataclass(frozen=True, kw_only=True)
class Assets:
    """A complete set of game assets and constants.

    If assets are invalid, constructor raises `pydantic.ValidationError`.
    """

    n_players: PositiveInt
    """The number of players in this particular game setup."""
    n_coins_on_start: NonNegativeInt
    """The number of coins at the start of the game."""
    n_selectable_combos: PositiveInt
    """The number of revealed combos at any given time."""
    n_turns: PositiveInt
    """The number of turns, after which the game ends."""
    abilities: list[Ability]
    """A list of abilities available in the game."""
    races: list[Race]
    """A list of races available in the game."""
    map: Map
    """The game map."""
    name: str = "<no name provided>"
    description: str = "<no description provided>"

    @model_validator(mode="after")  # type:ignore  # idk why it complains
    def _validate_n_selectable_combos(self) -> "Assets":
        n_players = self.n_players
        n_selectable_combos = self.n_selectable_combos
        n_races = len(self.races)
        safe_n_races = 2 * n_players + n_selectable_combos
        if n_races < safe_n_races:
            raise ValueError(
                f"{n_races} races are not enough to always guarantee "
                f"{n_selectable_combos} selectable combos for {n_players} "
                f"players, need at least {safe_n_races} races"
            )
        n_abilities = len(self.abilities)
        safe_n_abilities = n_players + n_selectable_combos
        if n_abilities < safe_n_abilities:
            raise ValueError(
                f"{n_abilities} abilities are not enough to always guarantee "
                f"{n_selectable_combos} selectable combos for {n_players} "
                f"players, need at least {safe_n_abilities} abilities"
            )
        return self


# ----------------------------- Runtime game data -----------------------------

class Combo:
    """Immutable pair of `Race` and `Ability` banners.

    Also contains a mutable amount of `coins` put on top during the game.
    """

    def __init__(self, race: Race, ability: Ability) -> None:
        """Construct a freshly revealed `Race`+`Ability` combo."""
        self.race = race
        self.ability = ability
        self.base_n_tokens = min(race.n_tokens + ability.n_tokens,
                                 race.max_n_tokens)
        self.coins: int = 0


class Player:
    """A bunch of "dumb" mutable stats, related to the same player.

    Even though these stats are mutated during the game,
    they aren't supposed to be directly modified by library users.
    """

    def __init__(self, coins: int) -> None:
        """Initialize `Player` with an initial supply of `coins`."""
        self.active_ability: Ability | None = None
        self.active_race: Race | None = None
        self.decline_race: Race | None = None
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


# ---------------------- Common interfaces / base classes ---------------------

class GameState:
    """An interface for accessing the `Game` state."""

    # I am lazy, to this class is not abstract,
    # it's simultaneously an interface and an implementation.
    # The constructor shouldn't be a part of the interface, but whatever.

    def __init__(self, assets: Assets) -> None:
        """Initialize the game state from `assets`."""
        # Gotta make a copy because we're going to mutate `Region`s.
        self._regions = deepcopy(assets.map.tiles)
        self._borders = [set[int]() for _ in range(len(self._regions))]
        for region1, region2 in assets.map.tile_borders:
            self._borders[region1].add(region2)
            self._borders[region2].add(region1)
        self._n_turns = assets.n_turns
        self._current_turn: int = 1
        abilities = iter(assets.abilities)
        races = iter(assets.races)
        visible_ra = islice(zip(races, abilities), assets.n_selectable_combos)
        self._combos = [Combo(r, a) for r, a in visible_ra]
        self._invisible_abilities = deque(abilities)
        self._invisible_races = deque(races)
        self._players = \
            [Player(assets.n_coins_on_start) for _ in range(assets.n_players)]
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
    def is_in_redeployment_turn(self) -> bool:
        """Whether the redeployment preudo turn is happening right now."""
        return self._turn_stage == _TurnStage.REDEPLOYMENT_TURN

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

    def owner_of(self, region: int) -> int | None:
        """Return the owner of the given `region` or `None` if there's none."""
        for i, p in enumerate(self.players):
            if p._is_owning(region):
                return i
        return None


class RulesViolation(Exception):
    """Base class for all domain errors yielded from rule plugins.

    Note that these don't include programming erros such as passing an invalid
    region index. For those, `ValueError` is usually used.
    """


class AbstractRules(ABC):
    """Interface that all `Rules` plugins must implement."""

    @abstractmethod
    def __init__(self, game: GameState) -> None:
        """Create an instance that will work on provided `game` instance."""
        ...

    @abstractmethod
    def check_decline(self) -> Iterator[RulesViolation]:
        """Yield `RulesViolation`s for `decline()`, if any."""
        ...

    @abstractmethod
    def check_select_combo(self, combo_index: int
                           ) -> Iterator[ValueError | RulesViolation]:
        """Yield `RulesViolation`s for `select_combo()`, if any.

        Before that, yield `ValueError` if
        `combo_index not in range(len(game.combos))`.
        """
        ...

    @abstractmethod
    def check_abandon(self, region: int
                      ) -> Iterator[ValueError | RulesViolation]:
        """Yield `RulesViolation`s for `abandon()`, if any.

        Before that, yield `ValueError` if
        `region not in range(len(game.regions))`.
        """
        ...

    @abstractmethod
    def check_conquer(self, region: int, *, use_dice: bool
                      ) -> Iterator[ValueError | RulesViolation]:
        """Yield `RulesViolation`s for `conquer()`, if any.

        Before that, yield `ValueError` if
        `region not in range(len(game.regions))`.
        """
        ...

    @abstractmethod
    def check_start_redeployment(self) -> Iterator[RulesViolation]:
        """Yield `RulesViolation`s for `start_redeployment()`, if any."""
        ...

    @abstractmethod
    def check_deploy(self, n_tokens: int, region: int
                     ) -> Iterator[ValueError | RulesViolation]:
        """Yield `RulesViolation`s for `deploy()`, if any.

        Before that, yield `ValueError` if
        `n_tokens < 1 or region not in range(len(game.regions))`.
        """
        ...

    @abstractmethod
    def check_end_turn(self) -> Iterator[RulesViolation]:
        """Yield `RulesViolation`s for `end_turn()`, if any."""
        ...

    @abstractmethod
    def conquest_cost(self, region: int) -> int:
        """Return the amount of tokens needed to conquer the given `region`.

        Assume that `region` is a valid conquest target.
        """
        ...

    @abstractmethod
    def calculate_turn_reward(self) -> int:
        """Calculate the amount of coins to be paid for the passed turn."""
        ...
