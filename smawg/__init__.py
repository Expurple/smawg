"""Backend engine for Small World board game.

See https://github.com/expurple/smawg for more info about the project.
"""

from smawg._engine import Game, Hooks, InvalidAssets, validate
from smawg._plugin_interface import (
    Ability, Combo, Player, Race, Region, RulesViolation
)

__all__ = [
    "Game", "Hooks", "InvalidAssets", "validate",
    "Ability", "Combo", "Player", "Race", "Region",
    "RulesViolation"
]
