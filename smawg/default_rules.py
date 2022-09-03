"""Rules that are used by `smawg.Game` by default.

See https://github.com/expurple/smawg for more info about the project.
"""

from smawg._plugin_interface import GameState, RulesViolation, _TurnStage

__all__ = [
    "Rules", "GameEnded", "NoActiveRace", "ForbiddenDuringRedeployment",
    "DecliningWhenActive", "SelectingOnDeclineTurn", "SelectingWhenActive",
    "NonControlledRegion", "AbandoningAfterConquests", "AlreadyUsedDice",
    "NotAtBorder", "ConqueringOwnRegion", "NonAdjacentRegion",
    "NoActiveRegions", "EndBeforeSelect", "NotEnoughCoins",
    "RollingWithoutTokens", "NotEnoughTokensToConquer",
    "NotEnoughTokensToRoll", "NotEnoughTokensToDeploy", "UndeployedTokens"
]


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

class Rules:
    """Rules that are used by `smawg.Game` by default."""

    def __init__(self, game: GameState) -> None:
        """Create an instance that will work on provided `game` instance."""
        self.game = game

    def check_decline(self) -> None:
        """Check if `decline()` violates the rules.

        Raise
        * `NoActiveRace`
            if the player is already in decline.
        * `DecliningWhenActive`
            if the player has already used his active race during this turn.
        * `ForbiddenDuringRedeployment`
            if this method is called during the redeployment phase.
        * `GameEnded`
            if this method is called after the game has ended.
        """
        self._assert_game_has_not_ended()
        self._assert_has_active_race()
        self._assert_not_in_redeployment()
        if self.game._turn_stage in (
                _TurnStage.ACTIVE, _TurnStage.CONQUESTS, _TurnStage.USED_DICE):
            raise DecliningWhenActive()

    def check_select_combo(self, combo_index: int) -> None:
        """Check if `select_combo()` violates the rules.

        Assume that `combo_index` is in valid range.

        Raise
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
        self._assert_game_has_not_ended()
        self._assert_not_in_redeployment()
        if self.game._turn_stage == _TurnStage.DECLINED:
            raise SelectingOnDeclineTurn()
        if self.game._turn_stage != _TurnStage.SELECT_COMBO:
            raise SelectingWhenActive()
        coins_getting = self.game.combos[combo_index].coins
        if combo_index > self.game.player.coins + coins_getting:
            raise NotEnoughCoins()

    def check_abandon(self, region: int) -> None:
        """Check if `abandon()` violates the rules.

        Assume that `region` is in valid range.

        Raise
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
        self._assert_game_has_not_ended()
        self._assert_has_active_race()
        self._assert_not_in_redeployment()
        if region not in self.game.player.active_regions:
            raise NonControlledRegion()
        if self.game._turn_stage in (_TurnStage.CONQUESTS,
                                     _TurnStage.USED_DICE):
            raise AbandoningAfterConquests()

    def check_conquer(self, region: int, *, use_dice: bool) -> None:
        """Check if `conquer()` violates the rules.

        Assume that `region` is in valid range.

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
            self._check_conquer_with_dice(region)
        else:
            self._check_conquer_without_dice(region)

    def check_start_redeployment(self) -> None:
        """Check if `start_redeployment()` violates the rules.

        Raise
        * `NoActiveRace`
            if the player doesn't have an active race.
        * `NoActiveRegions`
            if the player doesn't control any regions with his active race.
        * `ForbiddenDuringRedeployment`
            if this method is called during the redeployment phase.
        * `GameEnded`
            if this method is called after the game has ended.
        """
        self._assert_game_has_not_ended()
        self._assert_has_active_race()
        self._assert_not_in_redeployment()
        if not self.game.player.active_regions:
            raise NoActiveRegions()

    def check_deploy(self, n_tokens: int, region: int) -> None:
        """Check if `deploy()` violates the rules.

        Assume that `n_tokens` is positive and `region` is in valid range.

        Raise
        * `NoActiveRace`
            if the player doesn't have an active race.
        * `NonControlledRegion`
            if the player doesn't control the `region` with his active race.
        * `NotEnoughTokensToDeploy`
            if the player doesn't have `n_tokens` on hand.
        * `GameEnded`
            if this method is called after the game has ended.
        """
        self._assert_game_has_not_ended()
        self._assert_has_active_race()
        if region not in self.game.player.active_regions:
            raise NonControlledRegion()
        tokens_on_hand = self.game.player.tokens_on_hand
        if n_tokens > tokens_on_hand:
            raise NotEnoughTokensToDeploy(tokens_on_hand)

    def check_end_turn(self) -> None:
        """Check if `end_turn()` violates the rules.

        Raise
        * `EndBeforeSelect`
            if the player must select a new combo and haven't done that yet.
        * `UndeployedTokens`
            if player must deploy tokens from hand and haven't done that yet.
        * `GameEnded`
            if this method is called after the game has ended.
        """
        self._assert_game_has_not_ended()
        if self.game._turn_stage == _TurnStage.SELECT_COMBO:
            raise EndBeforeSelect()
        tokens_on_hand = self.game.player.tokens_on_hand
        if tokens_on_hand > 0:
            if self.game._turn_stage == _TurnStage.USED_DICE \
                    and len(self.game.player.active_regions) == 0:
                # The player has no regions and no ability to conquer, so
                # he can't possibly deploy his tokens. Don't raise the error.
                pass
            else:
                cd = self.game._turn_stage == _TurnStage.CAN_DECLINE
                raise UndeployedTokens(tokens_on_hand, can_decline=cd)

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
            raise RollingWithoutTokens()
        minimum_required = self.conquest_cost(region) - 3
        if tokens_on_hand < minimum_required:
            raise NotEnoughTokensToRoll(tokens_on_hand, minimum_required)

    def _check_conquer_without_dice(self, region: int) -> None:
        self._check_conquer_common(region)
        tokens_on_hand = self.game.player.tokens_on_hand
        tokens_required = self.conquest_cost(region)
        if tokens_on_hand < tokens_required:
            raise NotEnoughTokensToConquer(tokens_on_hand, tokens_required)

    def _check_conquer_common(self, region: int) -> None:
        """Common checks for all conquests (with or without dice)."""
        self._assert_game_has_not_ended()
        self._assert_has_active_race()
        self._assert_not_in_redeployment()
        if self.game._turn_stage == _TurnStage.USED_DICE:
            raise AlreadyUsedDice()
        if len(self.game.player.active_regions) == 0 \
                and not self.game.regions[region].is_at_map_border:
            raise NotAtBorder()
        if region in self.game.player.active_regions:
            raise ConqueringOwnRegion()
        has_adjacent = any(region in self.game._borders[own]
                           for own in self.game.player.active_regions)
        if len(self.game.player.active_regions) > 0 and not has_adjacent:
            raise NonAdjacentRegion()

    def _assert_game_has_not_ended(self) -> None:
        if self.game.has_ended:
            raise GameEnded()

    def _assert_has_active_race(self) -> None:
        if self.game.player.active_race is None:
            raise NoActiveRace()

    def _assert_not_in_redeployment(self) -> None:
        if self.game._turn_stage in \
                (_TurnStage.REDEPLOYMENT, _TurnStage.REDEPLOYMENT_TURN):
            raise ForbiddenDuringRedeployment()
