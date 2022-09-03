import smawg.exceptions as exc
from smawg._plugin_interface import _GameState, _TurnStage

__all__ = ["_Rules"]


class _Rules:
    """Implements the game rules."""

    def __init__(self, game: _GameState) -> None:
        """Create an instance that will work on provided `game` instance."""
        self.game = game

    def check_decline(self) -> None:
        """Raise `RulesViolation` if `decline()` violates the rules."""
        self._assert_game_has_not_ended()
        self._assert_has_active_race()
        self._assert_not_in_redeployment()
        if self.game._turn_stage in (
                _TurnStage.ACTIVE, _TurnStage.CONQUESTS, _TurnStage.USED_DICE):
            raise exc.DecliningWhenActive()

    def check_combo(self, combo_index: int) -> None:
        """Raise `RulesViolation` if `select_combo()` violates the rules.

        Assume that `combo_index` is in valid range.
        """
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
        """Raise `RulesViolation` if `abandon()` violates the rules.

        Assume that `region` is in valid range.
        """
        self._assert_game_has_not_ended()
        self._assert_has_active_race()
        self._assert_not_in_redeployment()
        if region not in self.game.player.active_regions:
            raise exc.NonControlledRegion()
        if self.game._turn_stage in (_TurnStage.CONQUESTS,
                                     _TurnStage.USED_DICE):
            raise exc.AbandoningAfterConquests()

    def check_conquer(self, region: int, *, use_dice: bool) -> None:
        """Raise `RulesViolation` if `conquer()` violates the rules.

        Assume that `region` is in valid range.
        """
        if use_dice:
            self._check_conquer_with_dice(region)
        else:
            self._check_conquer_without_dice(region)

    def check_start_redeployment(self) -> None:
        """Raise `RulesViolation` if `start_redeployment()` violates rules."""
        self._assert_game_has_not_ended()
        self._assert_has_active_race()
        self._assert_not_in_redeployment()
        if not self.game.player.active_regions:
            raise exc.NoActiveRegions()

    def check_deploy(self, n_tokens: int, region: int) -> None:
        """Raise `RulesViolation` if `deploy()` violates the rules.

        Assume that `n_tokens` is positive and `region` is in valid range.
        """
        self._assert_game_has_not_ended()
        self._assert_has_active_race()
        if region not in self.game.player.active_regions:
            raise exc.NonControlledRegion()
        tokens_on_hand = self.game.player.tokens_on_hand
        if n_tokens > tokens_on_hand:
            raise exc.NotEnoughTokensToDeploy(tokens_on_hand)

    def check_end_turn(self) -> None:
        """Raise `RulesViolation` if `end_turn()` violates the rules."""
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
