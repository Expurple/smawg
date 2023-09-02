"""Basic Small World rules.

Without special effects from different terrain types, races or abilities.

Intented to be reused between different "editions" of the game.

See https://github.com/expurple/smawg for more info about the project.
"""

from typing import Iterator

from pydantic import NonNegativeInt, PositiveInt
from pydantic.dataclasses import dataclass

# Importing directly from `smawg` would cause a circular import.
from smawg._common import (
    AbstractRules, GameState, RulesViolation, _TurnStage as _TS
)

__all__ = [
    "Decline", "SelectCombo", "Abandon", "Conquer", "ConquerWithDice",
    "StartRedeployment", "Deploy", "EndTurn", "Action",
    "Rules", "GameEnded", "NoActiveRace", "ForbiddenDuringRedeployment",
    "DecliningWhenActive", "SelectingOnDeclineTurn", "SelectingWhenActive",
    "NonControlledRegion", "AbandoningAfterConquests", "AlreadyUsedDice",
    "NotAtBorder", "ConqueringOwnRegion", "NonAdjacentRegion",
    "NoActiveRegions", "EndBeforeSelect", "NotEnoughCoins",
    "RollingWithoutTokens", "NotEnoughTokensToConquer",
    "NotEnoughTokensToRoll", "NotEnoughTokensToDeploy", "UndeployedTokens"
]


# -----------------------------------------------------------------------------
#                                  Actions
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class Decline:
    """Put player's active race in decline state."""

    pass


@dataclass(frozen=True)
class SelectCombo:
    """Select the combo at specified `combo_index` as active."""

    combo_index: NonNegativeInt


@dataclass(frozen=True)
class Abandon:
    """Abandon the given map `region`."""

    region: NonNegativeInt


@dataclass(frozen=True)
class Conquer:
    """Conquer the given map `region` without using the reinforcements dice."""

    region: NonNegativeInt


@dataclass(frozen=True)
class ConquerWithDice:
    """Roll the reinforcements dice and attempt to conquer `region`."""

    region: NonNegativeInt


@dataclass(frozen=True)
class StartRedeployment:
    """Pick up tokens to redeploy, leaving 1 token in each owned region."""

    pass


@dataclass(frozen=True)
class Deploy:
    """Deploy `n_tokens` from hand to the specified own `region`."""

    n_tokens: PositiveInt
    region: NonNegativeInt


@dataclass(frozen=True)
class EndTurn:
    """End turn (full or redeployment) and give control to the next player."""

    pass


Action = Decline | SelectCombo | Abandon | Conquer | ConquerWithDice | \
    StartRedeployment | Deploy | EndTurn
"""A sum type of all Actions."""


# -----------------------------------------------------------------------------
#                                 Exceptions
# -----------------------------------------------------------------------------

class _RaisesConstMessage(RulesViolation):
    """Base class for all exceptions with a constant message.

    Allows to reuse its constructor and inherit without boilerplate code.
    """

    MESSAGE: str = "A friendly message for the user. " \
                   "Override this in clild classes."

    def __init__(self) -> None:
        """Constuct an exception with `self.MESSAGE` as `args[0]`."""
        super().__init__(self.MESSAGE)


# ---------------------- RaisesConstMessage subclasses ------------------------

class GameEnded(_RaisesConstMessage):
    """Player tries to perform actions after the game has ended."""

    MESSAGE = "The game is over, this action is not available anymore"


class NoActiveRace(_RaisesConstMessage):
    """Player doesn't control any race, but it's required by the action."""

    MESSAGE = "To do this, you need to control an active race"


class ForbiddenDuringRedeployment(_RaisesConstMessage):
    """Player performes an action that's not allowed during redeployment."""

    MESSAGE = "This action is not allowed during redeployment"


class DecliningWhenActive(_RaisesConstMessage):
    """Attempting to decline after using the active race on the same turn."""

    MESSAGE = "You've already used your active race during this turn. " \
              "You can only decline during the next turn"


class SelectingOnDeclineTurn(_RaisesConstMessage):
    """Selecting combo after declining on the same turn."""

    MESSAGE = "You need to finish your turn now and select a new race " \
              "during the next turn"


class SelectingWhenActive(_RaisesConstMessage):
    """Selecting a new active race when the player already has one."""

    MESSAGE = "You need to decline first"


class NonControlledRegion(_RaisesConstMessage):
    """Player doesn't control the specified region with his active race."""

    MESSAGE = "The region must be controlled by your active race"


class AbandoningAfterConquests(_RaisesConstMessage):
    """Attempt to abandon a region after making conquests on the same turn."""

    MESSAGE = "You can't abandon regions after making conquests"


class AlreadyUsedDice(_RaisesConstMessage):
    """Attempt to conquer a region after using the dice on the same turn."""

    MESSAGE = "You've already rolled the dice during this turn " \
              "and can't make any more conquests"


class NotAtBorder(_RaisesConstMessage):
    """The first conquest of a new race is not at the map border."""

    MESSAGE = "The initial conquest must be at the map border"


class ConqueringOwnRegion(_RaisesConstMessage):
    """Conquering a region that's occupied by player's own active race."""

    MESSAGE = "Can't conquer your own region"


class NonAdjacentRegion(_RaisesConstMessage):
    """Conquering a region that isn't adjacent to any owned regions."""

    MESSAGE = "The region must be adjacent to any of your active regions"


class NoActiveRegions(_RaisesConstMessage):
    """Player doesn't control any regions with his active race."""

    MESSAGE = "You must control at least one active region"


class EndBeforeSelect(_RaisesConstMessage):
    """Ending the turn before selecting a new race+ability combo."""

    MESSAGE = "You need to select a new race+ability combo " \
              "before ending this turn"


class NotEnoughCoins(_RaisesConstMessage):
    """Selecting a race without having enough coins to pay for it."""

    MESSAGE = "Not enough coins, select a different race"


class RollingWithoutTokens(_RaisesConstMessage):
    """Player tries to roll the dice while having 0 tokens on hand."""

    MESSAGE = "To roll the dice, you need to have at least 1 token on hand"


# ----------------------- Parameterized exceptions ----------------------------

class NotEnoughTokensToConquer(RulesViolation):
    """Player doesn't have enough tokens to conquer the region."""

    def __init__(self, tokens_on_hand: int, tokens_required: int) -> None:
        """Constuct an exception with a friendly message as `args[0]`.

        Save `tokens_on_hand` and `tokens_required` as attributes.
        """
        self.tokens_on_hand = tokens_on_hand
        self.tokens_required = tokens_required
        super().__init__(
            f"Not enough tokens on hand (you have {tokens_on_hand}, "
            f"but need {tokens_required})"
        )


class NotEnoughTokensToRoll(RulesViolation):
    """Player needs more than 3 additional tokens to conquer the region."""

    def __init__(self, tokens_on_hand: int, minimum_required: int) -> None:
        """Constuct an exception with a friendly message as `args[0]`.

        Save `tokens_on_hand` and `minimum_required` as attributes.

        `minimum_required` means "conquest cost minus 3".
        """
        self.tokens_on_hand = tokens_on_hand
        self.minimum_required = minimum_required
        super().__init__(
            f"Not enough tokens on hand (you have {tokens_on_hand}, "
            f"but need at least {minimum_required} to have a chance)"
        )


class NotEnoughTokensToDeploy(RulesViolation):
    """Player attempts to deploy more tokens than he has on hand."""

    def __init__(self, tokens_on_hand: int) -> None:
        """Constuct an exception with a friendly message as `args[0]`.

        Save `tokens_on_hand` as an attribute.
        """
        self.tokens_on_hand = tokens_on_hand
        super().__init__(
            f"Not enough tokens on hand (you have {tokens_on_hand})"
        )


class UndeployedTokens(RulesViolation):
    """Player attempts to end turn while having undeploed tokens on hand."""

    def __init__(self, tokens_on_hand: int, *, can_decline: bool) -> None:
        """Constuct an exception with a friendly message as `args[0]`.

        Save `tokens_on_hand` and `can_decline` as attributes.
        """
        self.tokens_on_hand = tokens_on_hand
        self.can_decline = can_decline
        or_maybe_decline = " or decline" if can_decline else ""
        super().__init__(
            f"You need to use remaining {tokens_on_hand} tokens on hand"
            f"{or_maybe_decline}"
        )


# -----------------------------------------------------------------------------
#                                   Rules
# -----------------------------------------------------------------------------

class Rules(AbstractRules):
    """Basic Small World rules.

    Without special effects from different terrain types, races or abilities.

    Intented to be reused between different "editions" of the game.
    """

    def __init__(self, game: GameState) -> None:
        """Create an instance that will work on provided `game` instance."""
        self._game = game

    def check_decline(self) -> Iterator[RulesViolation]:
        """Check if `decline()` violates the rules.

        Yield
        * `NoActiveRace`
            if the player is already in decline.
        * `DecliningWhenActive`
            if the player has already used his active race during this turn.
        * `ForbiddenDuringRedeployment`
            if this method is called during the redeployment phase.
        * `GameEnded`
            if this method is called after the game has ended.
        """
        if self._game.has_ended:
            yield GameEnded()
        if self._game.player.active_race is None:
            yield NoActiveRace()
        match self._game._turn_stage:
            case _TS.REDEPLOYMENT | _TS.REDEPLOYMENT_TURN:
                yield ForbiddenDuringRedeployment()
            case _TS.ACTIVE | _TS.CONQUESTS | _TS.USED_DICE:
                yield DecliningWhenActive()

    def check_select_combo(self, combo_index: int
                           ) -> Iterator[ValueError | RulesViolation]:
        """Check if `select_combo()` violates the rules.

        Yield
        * `ValueError`
            if `combo_index not in range(len(game.combos))`.
        * `SelectingWhenActive`
            if the player already has an active race.
        * `SelectingOnDeclineTurn`
            if the player has just declined during this turn.
        * `NotEnoughCoins`
            if the player doesn't have enough coins.
        * `ForbiddenDuringRedeployment`
            if this method is called during the redeployment phase.
        * `GameEnded`
            if this method is called after the game has ended.
        """
        n_combos = len(self._game.combos)
        if combo_index not in range(n_combos):
            yield ValueError(f"combo_index must be between 0 and {n_combos}")
        if self._game.has_ended:
            yield GameEnded()
        match self._game._turn_stage:
            case _TS.REDEPLOYMENT | _TS.REDEPLOYMENT_TURN:
                yield ForbiddenDuringRedeployment()
            case _TS.DECLINED:
                yield SelectingOnDeclineTurn()
            case _TS.SELECT_COMBO:
                pass  # Filter out the correct case from the next pattern.
            case _:
                yield SelectingWhenActive()
        coins_getting = self._game.combos[combo_index].coins
        if combo_index > self._game.player.coins + coins_getting:
            yield NotEnoughCoins()

    def check_abandon(self, region: int
                      ) -> Iterator[ValueError | RulesViolation]:
        """Check if `abandon()` violates the rules.

        Yield
        * `ValueError`
            if `region not in range(len(game.regions))`.
        * `NoActiveRace`
            if the player doesn't have an active race.
        * `NonControlledRegion`
            if player doesn't control the `region` with his active race.
        * `AbandoningAfterConquests`
            if the player has made conquests during this turn.
        * `ForbiddenDuringRedeployment`
            if this method is called during the redeployment phase.
        * `GameEnded`
            if this method is called after the game has ended.
        """
        n_regions = len(self._game.regions)
        if region not in range(n_regions):
            yield ValueError(f"region must be between 0 and {n_regions}")
        if self._game.has_ended:
            yield GameEnded()
        if self._game.player.active_race is None:
            yield NoActiveRace()
        match self._game._turn_stage:
            case _TS.REDEPLOYMENT | _TS.REDEPLOYMENT_TURN:
                yield ForbiddenDuringRedeployment()
            case _TS.CONQUESTS | _TS.USED_DICE:
                yield AbandoningAfterConquests()
        if region not in self._game.player.active_regions:
            yield NonControlledRegion()

    def check_conquer(self, region: int, *, use_dice: bool
                      ) -> Iterator[ValueError | RulesViolation]:
        """Check if `conquer()` violates the rules.

        Yield
        * `ValueError`
            if `region not in range(len(game.regions))`.
        * `NoActiveRace`
            if the player doesn't have an active race.
        * `NotAtBorder`
            if the first conquest of a new race is not at the map border.
        * `NonAdjacentRegion`
            if `region` isn't adjacent to any owned regions.
        * `ConqueringOwnRegion`
            if `region` is occupied by player's own active race.
        * `NotEnoughTokensToConquer`
            if conquering without dice and without enough tokens on hand.
        * `RollingWithoutTokens`
            if conquering with dice while having 0 tokens on hand.
        * `NotEnoughTokensToRoll`
            if conquering with dice, while needing >3 additional tokens.
        * `NotEnoughTokensToRoll`
            if conquering again after rolling the reinforcements dice.
        * `ForbiddenDuringRedeployment`
            if this method is called during the redeployment phase.
        * `GameEnded`
            if this method is called after the game has ended.
        """
        if use_dice:
            yield from self._check_conquer_with_dice(region)
        else:
            yield from self._check_conquer_without_dice(region)

    def check_start_redeployment(self) -> Iterator[RulesViolation]:
        """Check if `start_redeployment()` violates the rules.

        Yield
        * `NoActiveRace`
            if the player doesn't have an active race.
        * `NoActiveRegions`
            if the player doesn't control any regions with his active race.
        * `ForbiddenDuringRedeployment`
            if this method is called during the redeployment phase.
        * `GameEnded`
            if this method is called after the game has ended.
        """
        if self._game.has_ended:
            yield GameEnded()
        if self._game.player.active_race is None:
            yield NoActiveRace()
        if self._game._turn_stage in (_TS.REDEPLOYMENT, _TS.REDEPLOYMENT_TURN):
            yield ForbiddenDuringRedeployment()
        if not self._game.player.active_regions:
            yield NoActiveRegions()

    def check_deploy(self, n_tokens: int, region: int
                     ) -> Iterator[ValueError | RulesViolation]:
        """Check if `deploy()` violates the rules.

        Yield
        * `ValueError`
            if `n_tokens < 1 or region not in range(len(game.regions))`
        * `NoActiveRace`
            if the player doesn't have an active race.
        * `NonControlledRegion`
            if the player doesn't control the `region` with his active race.
        * `NotEnoughTokensToDeploy`
            if the player doesn't have `n_tokens` on hand.
        * `GameEnded`
            if this method is called after the game has ended.
        """
        if n_tokens < 1:
            yield ValueError("n_tokens must be greater then 0")
        n_regions = len(self._game.regions)
        if region not in range(n_regions):
            yield ValueError(f"region must be between 0 and {n_regions}")
        if self._game.has_ended:
            yield GameEnded()
        if self._game.player.active_race is None:
            yield NoActiveRace()
        if region not in self._game.player.active_regions:
            yield NonControlledRegion()
        tokens_on_hand = self._game.player.tokens_on_hand
        if n_tokens > tokens_on_hand:
            yield NotEnoughTokensToDeploy(tokens_on_hand)

    def check_end_turn(self) -> Iterator[RulesViolation]:
        """Check if `end_turn()` violates the rules.

        Yield
        * `EndBeforeSelect`
            if the player must select a new combo and haven't done that yet.
        * `UndeployedTokens`
            if player must deploy tokens from hand and haven't done that yet.
        * `GameEnded`
            if this method is called after the game has ended.
        """
        if self._game.has_ended:
            yield GameEnded()
        if self._game._turn_stage == _TS.SELECT_COMBO:
            yield EndBeforeSelect()
        tokens_on_hand = self._game.player.tokens_on_hand
        if tokens_on_hand > 0:
            if self._game._turn_stage == _TS.USED_DICE \
                    and len(self._game.player.active_regions) == 0:
                # The player has no regions and no ability to conquer, so
                # he can't possibly deploy his tokens. Don't yield the error.
                pass
            else:
                can_decline = (self._game._turn_stage == _TS.CAN_DECLINE)
                yield UndeployedTokens(tokens_on_hand, can_decline=can_decline)

    def conquest_cost(self, region: int) -> int:
        """Return the amount of tokens needed to conquer the given `region`.

        Assume that `region` is a valid conquest target.
        """
        cost = 3
        owner_idx = self._game.owner_of(region)
        if owner_idx is not None:
            owner = self._game.players[owner_idx]
            cost += owner.active_regions.get(region, 1)  # 1 if declined
        elif self._game.regions[region].has_a_lost_tribe:
            cost += 1
        return cost

    def calculate_turn_reward(self) -> int:
        """Calculate the amount of coins to be paid for the passed turn."""
        player = self._game.player
        return len(player.active_regions) + len(player.decline_regions)

    def _check_conquer_with_dice(self, region: int
                                 ) -> Iterator[ValueError | RulesViolation]:
        yield from self._check_conquer_common(region)
        tokens_on_hand = self._game.player.tokens_on_hand
        if tokens_on_hand < 1:
            yield RollingWithoutTokens()
        minimum_required = self.conquest_cost(region) - 3
        if tokens_on_hand < minimum_required:
            yield NotEnoughTokensToRoll(tokens_on_hand, minimum_required)

    def _check_conquer_without_dice(self, region: int
                                    ) -> Iterator[ValueError | RulesViolation]:
        yield from self._check_conquer_common(region)
        tokens_on_hand = self._game.player.tokens_on_hand
        tokens_required = self.conquest_cost(region)
        if tokens_on_hand < tokens_required:
            yield NotEnoughTokensToConquer(tokens_on_hand, tokens_required)

    def _check_conquer_common(self, region: int
                              ) -> Iterator[ValueError | RulesViolation]:
        """Common checks for all conquests (with or without dice)."""
        n_regions = len(self._game.regions)
        if region not in range(n_regions):
            yield ValueError(f"region must be between 0 and {n_regions}")
        if self._game.has_ended:
            yield GameEnded()
        if self._game.player.active_race is None:
            yield NoActiveRace()
        match self._game._turn_stage:
            case _TS.REDEPLOYMENT | _TS.REDEPLOYMENT_TURN:
                yield ForbiddenDuringRedeployment()
            case _TS.USED_DICE:
                yield AlreadyUsedDice()
        active_regions = frozenset(self._game.player.active_regions)
        is_at_map_border = self._game.regions[region].is_at_map_border
        if len(active_regions) == 0 and not is_at_map_border:
            yield NotAtBorder()
        if region in active_regions:
            yield ConqueringOwnRegion()
        around_target = self._game.assets.map.adjacent[region]
        if len(active_regions) > 0 and not (active_regions & around_target):
            yield NonAdjacentRegion()
