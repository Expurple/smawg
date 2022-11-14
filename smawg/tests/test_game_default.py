"""Tests for `smawg.default_rules` which aren't present in `smawg.basic_rules`.

This module can also be seen as a collection of `smawg` usage examples.
"""

import unittest
from copy import deepcopy

import smawg.basic_rules as br
import smawg.default_rules as dr
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

    def test_sea_and_lake(self) -> None:
        """Check if conquering a Sea or a Lake raises an error."""
        assets = deepcopy(TINY_ASSETS)
        assets["map"]["tiles"][0]["terrain"] = "Sea"
        assets["map"]["tiles"][1]["terrain"] = "Lake"
        game = Game(assets, shuffle_data=False)
        game.select_combo(0)
        with self.assertRaises(dr.ConqueringSeaOrLake):
            game.conquer(0)
        with self.assertRaises(dr.ConqueringSeaOrLake):
            game.conquer(1)

    def test_shore_of_border_sea(self) -> None:
        """Check if conquering a shore of border Sea doesn't raise an error."""
        # A donut shaped map: a Forest tile surrounded by a single Sea tile.
        assets = deepcopy(TINY_ASSETS)
        assets["map"] = {
            "tiles": [
                {
                    "has_a_lost_tribe": False,
                    "is_at_map_border": True,
                    "terrain": "Sea"
                },
                {
                    "has_a_lost_tribe": False,
                    "is_at_map_border": False,
                    "terrain": "Forest"
                }
            ],
            "tile_borders": [
                [0, 1]
            ]
        }
        game = Game(assets, shuffle_data=False)
        game.select_combo(0)
        # With `basic_rules`, this would raise an error.
        # But here with `default_rules`, it shouldn't.
        game.conquer(1)


if __name__ == "__main__":
    unittest.main()
