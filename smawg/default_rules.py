"""Rules that are used by `smawg.Game` by default.

See https://github.com/expurple/smawg for more info about the project.
"""

import smawg.basic_rules as br

__all__ = ["ConqueringSeaOrLake", "Rules"]


# -----------------------------------------------------------------------------
#                                 Exceptions
# -----------------------------------------------------------------------------

class ConqueringSeaOrLake(br._RaisesConstMessage):
    """Attempt to conquer a Sea or Lake region."""

    MESSAGE = "Seas and Lakes cannot be conquered"


# -----------------------------------------------------------------------------
#                                   Rules
# -----------------------------------------------------------------------------

class Rules(br.Rules):
    """Rules that are used by `smawg.Game` by default."""

    # Under the hood, basic rules are inherited from `smawg.basic_rules.Rules`.
    # This class implements specific rules
    # for each race, ability and terrain type.

    def check_conquer(self, region: int, *, use_dice: bool) -> None:
        """Check if `conquer()` violates the rules.

        Assume that `region` is in valid range.

        Propagate any `RulesViolation` from
        `smawg.basic_rules.Rules.check_conquer()`.

        Raise `ConqueringSeaOrLake`
        if the player attempts to conquer a Sea or a Lake.
        """
        super().check_conquer(region, use_dice=use_dice)
        if self._game.regions[region].terrain in ("Sea", "Lake"):
            raise ConqueringSeaOrLake()

    def conquest_cost(self, region: int) -> int:
        """Return the amount of tokens needed to conquer the given `region`.

        Assume that `region` is a valid conquest target.
        """
        cost = super().conquest_cost(region)
        if self._game.regions[region].terrain == "Mountain":
            cost += 1
        return cost
