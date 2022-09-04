"""Common types used both by rules plugins and `Game`.

See https://github.com/expurple/smawg for more info about the project.
"""

from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from enum import auto, Enum
from itertools import islice
from typing import Any


__all__ = [
    "Region", "Ability", "Race", "Combo", "Player", "_TurnStage", "GameState",
    "RulesViolation", "AbstractRules"
]


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


class GameState:
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

    def _owner(self, region: int) -> int | None:
        """Return the owner of the given `region` or `None` if there's none."""
        for i, p in enumerate(self.players):
            if p._is_owning(region):
                return i
        return None


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


class RulesViolation(Exception):
    """Base class for all exceptions raised from rule plugins."""


class AbstractRules(ABC):
    """Interface that all `Rules` plugins must implement."""

    @abstractmethod
    def __init__(self, game: GameState) -> None:
        """Create an instance that will work on provided `game` instance."""
        ...

    @abstractmethod
    def check_decline(self) -> None:
        """Check if `decline()` violates the rules.

        Raise `RulesViolation` if it does.
        """
        ...

    @abstractmethod
    def check_select_combo(self, combo_index: int) -> None:
        """Check if `select_combo()` violates the rules.

        Raise `RulesViolation` if it does.

        Assume that `combo_index` is in valid range.
        """
        ...

    @abstractmethod
    def check_abandon(self, region: int) -> None:
        """Check if `abandon()` violates the rules.

        Raise `RulesViolation` if it does.

        Assume that `region` is in valid range.
        """
        ...

    @abstractmethod
    def check_conquer(self, region: int, *, use_dice: bool) -> None:
        """Check if `conquer()` violates the rules.

        Raise `RulesViolation` if it does.

        Assume that `region` is in valid range.
        """
        ...

    @abstractmethod
    def check_start_redeployment(self) -> None:
        """Check if `start_redeployment()` violates the rules.

        Raise `RulesViolation` if it does.
        """
        ...

    @abstractmethod
    def check_deploy(self, n_tokens: int, region: int) -> None:
        """Check if `deploy()` violates the rules.

        Raise `RulesViolation` if it does.

        Assume that `n_tokens` is positive and `region` is in valid range.
        """
        ...

    @abstractmethod
    def check_end_turn(self) -> None:
        """Check if `end_turn()` violates the rules.

        Raise `RulesViolation` if it does.
        """
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
