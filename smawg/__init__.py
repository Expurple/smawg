"""Backend engine for Small World board game.

See https://github.com/expurple/smawg for more info about the project.
"""

import random
from collections import defaultdict
from dataclasses import replace
from typing import Any, Callable, Literal, Type, TypedDict, cast, overload

from pydantic import TypeAdapter

from smawg._common import (
    Ability, AbstractRules, Assets, Combo, GameState,
    Map, Player, Race, Region, RulesViolation, _TurnStage
)
from smawg.default_rules import Rules as DefaultRules

__all__ = [
    # Defined in this file:
    "Game", "Hooks", "validate",
    # Re-exported from smawg._common:
    "Region", "Ability", "Race", "Map", "Assets", "Combo", "Player",
    "GameState", "RulesViolation", "AbstractRules"
]


def validate(assets: dict[str, Any], *, strict: bool = False) -> None:
    """Raise `pydantic.ValidationError` if given `assets` are invalid.

    Parameter `strict` is deprecated and doesn't do anything.
    """
    _ = TypeAdapter(Assets).validate_python(assets)


def _shuffle(assets: Assets) -> Assets:
    """Shuffle the order of `Race` and `Ability` banners in `assets`.

    Just like you would do in a physical Small World game.

    Returns a copy as shallow as possible. Resulting `races` and `abilities`
    are new lists with references to the same objects. Other fields also
    reference the same objects.
    """
    races = list(assets.races)
    abilities = list(assets.abilities)
    random.shuffle(races)
    random.shuffle(abilities)
    return replace(assets, races=races, abilities=abilities)


def _roll_dice() -> int:
    """Return a random dice roll result."""
    return random.choice((0, 0, 0, 1, 2, 3))


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
    * Access to the rule checker, allowing to "dry run" an action
        and check if it's valid.

    Method calls automatically update `Game` state according to the rules,
    or raise exceptions if the call violates the rules.
    """

    # Under the hood, rules are implemented in `RulesT`
    # and properties are implemented in the base class.
    # This class only implements game actions and hooks.

    def __init__(self, assets: Assets | dict[str, Any],
                 RulesT: Type[AbstractRules] = DefaultRules, *,
                 shuffle_data: bool = True,
                 dice_roll_func: Callable[[], int] = _roll_dice,
                 hooks: Hooks = {}) -> None:
        """Initialize a game based on given `assets`.

        `assets` are converted to `Assets` if necessary.
        When `assets` are invalid, this will raise `pydantic.ValidationError`.

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
        if not isinstance(assets, Assets):
            assets = TypeAdapter(Assets).validate_python(assets)
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

    @property
    def rules(self) -> AbstractRules:
        """Access the rule checker.

        This is useful if you want to test an action without actually
        performing it.
        """
        return self._rules

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
        self._reveal_next_combo()
        self._turn_stage = _TurnStage.DECLINED

    def select_combo(self, combo_index: int) -> None:
        """Select the combo at specified `combo_index` as active.

        During that:
        * The player gets all coins that have been put on that combo.
        * Puts 1 coin on each combo above that (`combo_index` coins in total).
        * Then, the next combo is revealed.

        Raise the first error from `Rules.check_select_combo()`.
        """
        for e in self._rules.check_select_combo(combo_index):
            raise e
        self._pay_for_combo(combo_index)
        chosen_combo = self.combos.pop(combo_index)
        self.player._set_active(chosen_combo)
        self._turn_stage = _TurnStage.ACTIVE
        self._reveal_next_combo()

    def abandon(self, region: int) -> None:
        """Abandon the given map `region`.

        Raise the first error from `Rules.check_abandon()`.
        """
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

        Raise the first error from `Rules.check_conquer()`.
        """
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

        Raise the first error from `Rules.check_deploy()`.
        """
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

    def _reveal_next_combo(self) -> None:
        if len(self.combos) == self._assets.n_selectable_combos \
                or len(self._invisible_abilities) == 0 \
                or len(self._invisible_races) == 0:
            return
        next_race = self._invisible_races.popleft()
        next_ability = self._invisible_abilities.popleft()
        self.combos.append(Combo(next_race, next_ability))

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
        owner_idx = self.owner_of(region)
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
