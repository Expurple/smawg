"""Backend engine for Small World board game.

See https://github.com/expurple/smawg for more info about the project.
"""

import json
import random
from collections import defaultdict
from typing import Any, Callable, Literal, Type, TypedDict, cast, overload

import jsonschema

from smawg._common import (
    Ability, AbstractRules, Combo, GameState,
    Player, Race, Region, RulesViolation, _TurnStage
)
from smawg._metadata import SCHEMA_DIR
from smawg.default_rules import Rules as DefaultRules

__all__ = [
    # Defined in this file:
    "Game", "Hooks", "InvalidAssets", "validate",
    # Re-exported from smawg._common:
    "Ability", "AbstractRules", "Combo", "GameState",
    "Player", "Race", "Region", "RulesViolation"
]


# --------------------------- assets validation -------------------------------

with open(f"{SCHEMA_DIR}/assets.json") as file:
    _ASSETS_SCHEMA: dict[str, Any] = json.load(file)

_STRICT_ASSETS_SCHEMA = {**_ASSETS_SCHEMA, "additionalProperties": False}

_LOCAL_REF_RESOLVER = jsonschema.RefResolver(f"file://{SCHEMA_DIR}/", {})
"""Fixes references to local schemas."""


class InvalidAssets(Exception):
    """Assets match the JSON schema but still violate some invariants."""


def validate(assets: dict[str, Any], *, strict: bool = False) -> None:
    """Validate the game assets.

    Raise `jsonschema.exceptions.ValidationError`
    if `assets` don't match the schema in `assets_schema/`.

    If `strict=True`, also fail on undocumented keys.

    Raise `smawg.InvalidAssets` if
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
        raise InvalidAssets(
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
        raise InvalidAssets(
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
            raise InvalidAssets(
                f"Tile border [{t1}, {t2}] references a non-existing tile: "
                f"{greater_index} (the map only has {n_tiles} tiles)"
            )


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


class Hooks(TypedDict, total=False):
    """`TypedDict` annotation for `Game` hooks."""

    on_turn_start: Callable[["Game"], None]
    on_dice_rolled: Callable[["Game", int, bool], None]
    on_turn_end: Callable[["Game"], None]
    on_redeploy: Callable[["Game"], None]
    on_game_end: Callable[["Game"], None]


class Game(GameState):
    """High-level representation of a single Small World game.

    Provides:
    * Flexible configuration on construction (see `__init__`).
    * API for performing in-game actions (as methods).
    * Access to the game state (as readonly properties).

    Method calls automatically update `Game` state according to the rules,
    or raise exceptions if the call violates the rules.
    """

    # Under the hood, rules are implemented in `RulesT`
    # and properties are implemented in the base class.
    # This class only implements game actions and hooks.

    def __init__(self, assets: dict[str, Any],
                 RulesT: Type[AbstractRules] = DefaultRules, *,
                 shuffle_data: bool = True,
                 dice_roll_func: Callable[[], int] = _roll_dice,
                 hooks: Hooks = {}) -> None:
        """Initialize a game based on given `assets`.

        `assets` are validated using `validate()`, all errors are propagated.

        When initialization is finished, the object is ready to be used by
        player 0. `"on_turn_start"` hook is fired immediately, if provided.

        Provide `RulesT` to play with custom rules (see `docs/rules.md`).

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
        self._rules: AbstractRules = RulesT(self)
        # Only after `self` has been fully initialized.
        self._hooks["on_turn_start"](self)

    def decline(self) -> None:
        """Put player's active race in decline state.

        Or raise the first `RulesViolation` from `Rules.check_decline()`.
        """
        for e in self._rules.check_decline():
            raise e
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

        Raise `ValueError` if `combo_index not in range(len(self.combos))`.

        Raise the first `RulesViolation` from `Rules.check_select_combo()`
        """
        if combo_index not in range(len(self.combos)):
            msg = f"combo_index must be between 0 and {len(self.combos)}"
            raise ValueError(msg)
        for e in self._rules.check_select_combo(combo_index):
            raise e
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

        Raise `ValueError` if `region not in range(len(self.regions))`.

        Raise the first `RulesViolation` from `Rules.check_abandon()`.
        """
        if region not in range(len(self.regions)):
            msg = f"region must be between 0 and {len(self.regions)}"
            raise ValueError(msg)
        for e in self._rules.check_abandon(region):
            raise e
        self.player.tokens_on_hand += self.player.active_regions.pop(region)
        self._turn_stage = _TurnStage.ACTIVE

    @overload
    def conquer(self, region: int, *, use_dice: Literal[True]) -> int:
        ...

    @overload
    def conquer(self, region: int, *, use_dice: Literal[False]) -> None:
        ...

    @overload
    def conquer(self, region: int, *, use_dice: bool = False) -> int | None:
        ...

    def conquer(self, region: int, *, use_dice: bool = False) -> int | None:
        """Conquer the given map `region`.

        When `use_dice=True` is given,
        attempt to use reinforcements and return the value rolled on the dice.
        Otherwise, don't use the dice and return `None`.

        Raise `ValueError` if `region not in range(len(self.regions))`.

        Raise the first `RulesViolation` from `Rules.check_conquer()`.
        """
        if region not in range(len(self.regions)):
            msg = f"region must be between 0 and {len(self.regions)}"
            raise ValueError(msg)
        for e in self._rules.check_conquer(region, use_dice=use_dice):
            raise e
        if use_dice:
            return self._conquer_with_dice(region)
        else:
            self._conquer_without_dice(region)
            return None

    def start_redeployment(self) -> None:
        """Pick up tokens to redeploy, leaving 1 token in each owned region.

        Raise the first `RulesViolation` from
        `Rules.check_start_redeployment()`.

        This action ends conquests. After this method is called,
        the player should deploy tokens from hand and then end the turn.
        """
        for e in self._rules.check_start_redeployment():
            raise e
        self.player._pick_up_tokens()
        self._turn_stage = _TurnStage.REDEPLOYMENT

    def deploy(self, n_tokens: int, region: int) -> None:
        """Deploy `n_tokens` from hand to the specified own `region`.

        Raise `ValueError`
        if `n_tokens < 1` or `region not in range(len(self.regions))`.

        Raise the first `RulesViolation` from `Rules.check_deploy()`.
        """
        if n_tokens < 1:
            raise ValueError("n_tokens must be greater then 0")
        if region not in range(len(self.regions)):
            msg = f"region must be between 0 and {len(self.regions)}"
            raise ValueError(msg)
        for e in self._rules.check_deploy(n_tokens, region):
            raise e
        self.player.tokens_on_hand -= n_tokens
        self.player.active_regions[region] += n_tokens
        if self._turn_stage == _TurnStage.CAN_DECLINE:
            self._turn_stage = _TurnStage.ACTIVE

    def end_turn(self) -> None:
        """End turn (full or redeployment) and give control to the next player.

        Automatically calculate+pay coin rewards and fire appropriate hooks.

        Raise the first `RulesViolation` from `Rules.check_end_turn()`.
        """
        for e in self._rules.check_end_turn():
            raise e
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

    def _conquer_with_dice(self, region: int) -> int:
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
        return dice_value

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
