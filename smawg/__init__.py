"""Backend engine for Small World board game.

See https://github.com/expurple/smawg for more info about the project.
"""

from smawg._engine import Game, Hooks, validate
from smawg._plugin_interface import Ability, Combo, Player, Race, Region
from smawg.exceptions import InvalidAssets, RulesViolation


__all__ = [
    "Game", "Hooks", "validate",
    "Ability", "Combo", "Player", "Race", "Region",
    "InvalidAssets", "RulesViolation"
]
