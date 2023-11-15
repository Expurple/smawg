"""Backend engine for Small World board game.

See https://github.com/expurple/smawg for more info about the project.
"""

import random
from collections import defaultdict
from typing import (
    Any, Callable, Literal, Type, TypedDict, assert_never, cast, overload
)

from pydantic import TypeAdapter

from smawg._common import (
    Ability, AbstractRules, Assets, Combo, GameState,
    Map, Player, Race, Region, RulesViolation, TurnStage
)
from smawg.basic_rules import (
    Abandon, Conquer, ConquerWithDice, Decline, Deploy, EndTurn, SelectCombo,
    StartRedeployment
)
from smawg.default_rules import Action, Rules as DefaultRules

__all__ = [
    # Defined in this file:
    "Game", "Hooks", "roll_dice", "validate",
    # Re-exported from smawg._common:
    "Region", "Ability", "Race", "Map", "Assets", "Combo", "Player",
    "TurnStage", "GameState", "RulesViolation", "AbstractRules"
]

_VoidAction = Abandon | Conquer | Decline | Deploy | EndTurn | SelectCombo | \
    StartRedeployment
"""Actions, for which Game methods return None."""


def validate(assets: dict[str, Any], *, strict: bool = False) -> None:
    """Raise `pydantic.ValidationError` if given `assets` are invalid.

    Parameter `strict` is deprecated and doesn't do anything.
    """
    _ = TypeAdapter(Assets).validate_python(assets)


def roll_dice(rng: random.Random | None = None) -> int:
    """Return a random dice roll result.

    If `rng` is given and not `None`, it is used instead of the global one.
    """
    dice_sides = [0, 0, 0, 1, 2, 3]
    if rng is not None:
        return rng.choice(dice_sides)
    else:
        return random.choice(dice_sides)


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
                 RulesT: Type[AbstractRules[Action]] = DefaultRules, *,
                 dice_roll_func: Callable[[], int] = roll_dice,
                 hooks: Hooks = {}) -> None:
        """Initialize a game based on given `assets`.

        `assets` are converted to `Assets` if necessary.
        When `assets` are invalid, this will raise `pydantic.ValidationError`.
        You may want to convert and `.shuffle()` `assets` in advance.

        When initialization is finished, the object is ready to be used by
        player 0. `"on_turn_start"` hook is fired immediately, if provided.

        Provide `RulesT` to play with custom rules (see `docs/rules.md`).

        Provide custom `dice_roll_func` to get pre-determined
        (or even dynamically controlled) dice roll results.

        Provide optional `hooks` to automatically fire on certain events.
        For details, see `docs/hooks.md`.
        """
        if not isinstance(assets, Assets):
            assets = TypeAdapter(Assets).validate_python(assets)
        super().__init__(assets)
        self._next_player_id = self._increment(self.player_id)
        """Helper to preserve `_current_player_id` during redeployment."""
        self._roll_dice = dice_roll_func
        self._hooks = cast(Hooks, defaultdict(lambda: _do_nothing, **hooks))
        # Only after all other fields have been initialized.
        self._rules: AbstractRules[Action] = RulesT(self)
        # Only after `self` has been fully initialized.
        self._hooks["on_turn_start"](self)

    @property
    def rules(self) -> AbstractRules[Action]:
        """Access the rule checker.

        This is useful if you want to test an action without actually
        performing it.
        """
        return self._rules

    @overload
    def do(self, action: ConquerWithDice) -> int:
        ...

    @overload
    def do(self, action: _VoidAction) -> None:
        ...

    def do(self, action: Action) -> int | None:
        """Execute the given `Action` or raise an error if it's not valid.

        For `ConquerWithDice`, return the value rolled on the dice.
        For other actions, return `None`.

        This method is an abstraction over all methods that perform individual
        actions. Refer to their docs for details of each action.
        """
        match action:
            case Decline():
                self.decline()
            case SelectCombo(combo_index):
                self.select_combo(combo_index)
            case Abandon(region):
                self.abandon(region)
            case Conquer(region):
                self.conquer(region, use_dice=False)
            case ConquerWithDice(region):
                return self.conquer(region, use_dice=True)
            case StartRedeployment():
                self.start_redeployment()
            case Deploy(n_tokens, region):
                self.deploy(n_tokens, region)
            case EndTurn():
                self.end_turn()
            case not_handled:
                assert_never(not_handled)
        return None

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

        _put_in_decline(self.player)
        self._reveal_next_combo()
        self._turn_stage = TurnStage.DECLINED

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
        _set_active(chosen_combo, self.player)
        self._turn_stage = TurnStage.ACTIVE
        self._reveal_next_combo()

    def abandon(self, region: int) -> None:
        """Abandon the given map `region`.

        Raise the first error from `Rules.check_abandon()`.
        """
        for e in self._rules.check_abandon(region):
            raise e
        self.player.tokens_on_hand += self.player.active_regions.pop(region)
        self._turn_stage = TurnStage.ACTIVE

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
        _pick_up_tokens(self.player)
        self._turn_stage = TurnStage.REDEPLOYMENT

    def deploy(self, n_tokens: int, region: int) -> None:
        """Deploy `n_tokens` from hand to the specified own `region`.

        Raise the first error from `Rules.check_deploy()`.
        """
        for e in self._rules.check_deploy(n_tokens, region):
            raise e
        self.player.tokens_on_hand -= n_tokens
        self.player.active_regions[region] += n_tokens
        if self.turn_stage == TurnStage.CAN_DECLINE:
            self._turn_stage = TurnStage.ACTIVE

    def end_turn(self) -> None:
        """End turn (full or redeployment) and give control to the next player.

        Automatically calculate+pay coin rewards and fire appropriate hooks.

        Raise the first `RulesViolation` from `Rules.check_end_turn()`.
        """
        for e in self._rules.check_end_turn():
            raise e
        if self.turn_stage != TurnStage.REDEPLOYMENT_TURN:
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
        self._turn_stage = TurnStage.CONQUESTS

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
        self._turn_stage = TurnStage.USED_DICE
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
                self._turn_stage = TurnStage.REDEPLOYMENT_TURN
                self._hooks["on_redeploy"](self)
                return
        # This part performs the actual switch to the next turn:
        self._player_id = self._next_player_id
        self._next_player_id = self._increment(self.player_id)
        if self.player_id == 0:
            self._current_turn += 1
        if self.player.active_race is None:
            self._turn_stage = TurnStage.SELECT_COMBO
        else:
            self._turn_stage = TurnStage.CAN_DECLINE
        if self.has_ended:
            self._hooks["on_game_end"](self)
        else:
            _pick_up_tokens(self.player)
            self._hooks["on_turn_start"](self)

    def _increment(self, player_id: int) -> int:
        """Increment the given `player_id`, wrapping around if needed."""
        return (player_id + 1) % len(self.players)


def _put_in_decline(player: Player) -> None:
    player.decline_regions = set(player.active_regions)
    player.active_regions.clear()
    player.tokens_on_hand = 0
    player.decline_race = player.active_race
    player.active_race = None
    player.active_ability = None


def _pick_up_tokens(player: Player) -> None:
    """Pick up available tokens, leaving 1 token in each owned region."""
    for region in player.active_regions:
        player.tokens_on_hand += player.active_regions[region] - 1
        player.active_regions[region] = 1


def _set_active(combo: Combo, player: Player) -> None:
    """Set `Race` and `Ability` from the given `combo` as active."""
    player.active_race = combo.race
    player.active_ability = combo.ability
    player.tokens_on_hand = combo.base_n_tokens
