"""Rules that are used by `smawg.Game` by default.

See https://github.com/expurple/smawg for more info about the project.
"""

from typing import Iterator

import smawg.basic_rules as br
# Importing directly from `smawg` would cause a circular import.
from smawg._common import RulesViolation

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

    def check_conquer(self, region: int, *, use_dice: bool
                      ) -> Iterator[ValueError | RulesViolation]:
        """Check if `conquer()` violates the rules.

        Propagate most errors from `smawg.basic_rules.Rules.check_conquer()`,
        but allow to start conquests from non-border shores of border Seas.

        Yield `ConqueringSeaOrLake`
        if the player attempts to conquer a Sea or a Lake.
        """
        for e in super().check_conquer(region, use_dice=use_dice):
            # Consider shores of border Seas as being on the map border.
            is_not_border = isinstance(e, br.NotAtBorder)
            if is_not_border and self._is_adjacent_to_border_sea(region):
                continue
            # Propagate all other errors from `basic_rules`.
            yield e
        # Forbid conquering Seas and Lakes.
        if self._game.regions[region].terrain in ("Sea", "Lake"):
            yield ConqueringSeaOrLake()

    def conquest_cost(self, region: int) -> int:
        """Return the amount of tokens needed to conquer the given `region`.

        Assume that `region` is a valid conquest target.
        """
        cost = super().conquest_cost(region)
        if self._game.regions[region].terrain == "Mountain":
            cost += 1
        return cost

    def _is_adjacent_to_border_sea(self, region: int) -> bool:
        for i in self._game._borders[region]:
            r = self._game.regions[i]
            if r.is_at_map_border and r.terrain == "Sea":
                return True
        return False
