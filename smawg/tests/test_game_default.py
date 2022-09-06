"""Tests for `smawg.default_rules` which aren't present in `smawg.basic_rules`.

This module can also be seen as a collection of `smawg` usage examples.
"""

import unittest
from copy import deepcopy

import smawg.basic_rules as br
from smawg import Game
from smawg.tests.common import BaseGameTest, TINY_ASSETS


class TestTerrain(BaseGameTest):
    """Tests for common terrain effects."""

    def test_mountain(self) -> None:
        """Check if conquering a Mountain requires 1 additional token."""
        # Set up tiles and give the player exactly 15 tokens.
        assets = deepcopy(TINY_ASSETS)
        assets["abilities"][0]["n_tokens"] = 0
        assets["races"][0]["max_n_tokens"] = 15
        assets["races"][0]["n_tokens"] = 15
        assets["map"]["tiles"][1]["terrain"] = "Mountain"
        assets["map"]["tiles"][2]["terrain"] = "Mountain"
        assets["map"]["tiles"][2]["has_a_lost_tribe"] = True
        assets["map"]["tiles"][3]["terrain"] = "Mountain"
        game = Game(assets, shuffle_data=False)
        game.select_combo(0)
        # Empty Forest.
        with self.assertConquers(game, 0, cost=3):
            game.conquer(0)
        # Empty Mountain.
        with self.assertConquers(game, 1, cost=4):
            game.conquer(1)
        # Mountain with a Lost Tribe.
        with self.assertConquers(game, 2, cost=5):
            game.conquer(2)
        # Enough tokens for one more empty Forest,
        # but not enough for a Mountain.
        self.assertEqual(game.player.tokens_on_hand, 3)
        with self.assertRaises(br.NotEnoughTokensToConquer):
            game.conquer(3)


if __name__ == "__main__":
    unittest.main()
