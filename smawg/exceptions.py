"""Domain exceptions raised by `smawg`.

Import from here if you need concrete subclasses of `RulesViolation`.

`InvalidAssets` and `RulesViolation` itself can be imported from `smawg`.

See https://github.com/expurple/smawg for more info about the project.
"""


# -----------------------------------------------------------------------------
#                  Exceptions for runtime rule violations
# -----------------------------------------------------------------------------


# ----------------------------- Base classes ----------------------------------

class RulesViolation(Exception):
    """Base class for all `smawg.exceptions` raised from `Game` methods."""

    MESSAGE: str = "A friendly message for the user. " \
                   "Override this in clild classes."


class _RaisesConstMessage(RulesViolation):
    """Base class for all `smawg.exceptions` that raise a constant message.

    Allows to reuse its constructor and inherit without boilerplate code.
    """

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

    MESSAGE = "Not enough tokens on hand (you have {tokens_on_hand}, " \
              "but need {tokens_required})"

    def __init__(self, tokens_on_hand: int, tokens_required: int) -> None:
        """Constuct an exception with a friendly message as `args[0]`.

        Save `tokens_on_hand` and `tokens_required` as attributes.
        """
        self.tokens_on_hand = tokens_on_hand
        self.tokens_required = tokens_required
        formatted_message = self.MESSAGE.format(**locals())
        super().__init__(formatted_message)


class NotEnoughTokensToRoll(RulesViolation):
    """Player needs more than 3 additional tokens to conquer the region."""

    MESSAGE = "Not enough tokens on hand (you have {tokens_on_hand}, " \
              "but need at least {minimum_required} to have a chance)"

    def __init__(self, tokens_on_hand: int, minimum_required: int) -> None:
        """Constuct an exception with a friendly message as `args[0]`.

        Save `tokens_on_hand` and `minimum_required` as attributes.

        `minimum_required` means "conquest cost minus 3".
        """
        self.tokens_on_hand = tokens_on_hand
        self.minimum_required = minimum_required
        formatted_message = self.MESSAGE.format(**locals())
        super().__init__(formatted_message)


class NotEnoughTokensToDeploy(RulesViolation):
    """Player attempts to deploy more tokens than he has on hand."""

    MESSAGE = "Not enough tokens on hand (you have {tokens_on_hand})"

    def __init__(self, tokens_on_hand: int) -> None:
        """Constuct an exception with a friendly message as `args[0]`.

        Save `tokens_on_hand` as an attribute.
        """
        self.tokens_on_hand = tokens_on_hand
        formatted_message = self.MESSAGE.format(**locals())
        super().__init__(formatted_message)


class UndeployedTokens(RulesViolation):
    """Player attempts to end turn while having undeploed tokens on hand."""

    MESSAGE = "You need to use remaining {tokens_on_hand} tokens on hand" \
              "{or_maybe_decline}"

    def __init__(self, tokens_on_hand: int, *, can_decline: bool) -> None:
        """Constuct an exception with a friendly message as `args[0]`.

        Save `tokens_on_hand` and `can_decline` as attributes.
        """
        self.tokens_on_hand = tokens_on_hand
        self.can_decline = can_decline
        or_maybe_decline = " or decline" if can_decline else ""
        formatted_message = self.MESSAGE.format(**locals())
        super().__init__(formatted_message)
