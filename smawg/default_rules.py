"""Rules that are used by `smawg.Game` by default.

See https://github.com/expurple/smawg for more info about the project.
"""

import smawg.basic_rules as br

__all__ = ["Rules"]


class Rules(br.Rules):
    """Rules that are used by `smawg.Game` by default."""

    # Under the hood, basic rules are inherited from `smawg.basic_rules.Rules`.
    # This class implements specific rules
    # for each race, ability and terrain type.

    def conquest_cost(self, region: int) -> int:
        """Return the amount of tokens needed to conquer the given `region`.

        Assume that `region` is a valid conquest target.
        """
        cost = super().conquest_cost(region)
        if self._game.regions[region].terrain == "Mountain":
            cost += 1
        return cost
