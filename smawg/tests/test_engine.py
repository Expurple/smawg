"""Tests for `smawg.engine` module.

This module can also be seen as a collection of usage examples.
"""

from contextlib import nullcontext

import jsonschema.exceptions

from smawg import _ASSETS_DIR
from smawg.engine import Ability, Game, GameEnded
from smawg.tests.common import BaseTest


class TestAbility(BaseTest):
    """Tests for `smawg.engine.Ability` class."""

    def test_valid_json(self):
        """Check if `Ability.__init__` propetly parses the given json."""
        ability = Ability({"name": "Some Name", "n_tokens": 4})
        self.assertEqual(ability.name, "Some Name")
        self.assertEqual(ability.n_tokens, 4)

    def test_invalid_jsons(self):
        """Check if `Ability.__init__` raises when given invalid jsons."""
        # Missing "name" and "n_tokens"
        self.assertInvalid({"random keys": "and values"})
        self.assertInvalid({})
        # Missing "name"
        self.assertInvalid({"n_tokens": "4"})
        # Missing "n_tokens"
        self.assertInvalid({"name": "Some Name"})
        # Invalid type of "n_tokens"
        self.assertInvalid({"name": "Some Name", "n_tokens": None})
        self.assertInvalid({"name": "Some Name", "n_tokens": "4"})
        # Invalid value of "n_tokens"
        self.assertInvalid({"name": "Some Name", "n_tokens": -4})

    def assertInvalid(self, json: dict):
        """Check if `Ability.__init__` raises when given this `json`."""
        with self.assertRaises(jsonschema.exceptions.ValidationError):
            _ = Ability(json)


class TestGame(BaseTest):
    """Tests for `smawg.engine.Game` class."""

    def test_tiny_game_scenario(self):
        """Run a full game based on `tiny.json` and check every step."""
        tiny_data = self.load_data(f"{_ASSETS_DIR}/tiny.json")
        game = Game(tiny_data, n_players=2)
        self.assertBalances(game, [1, 1])
        with nullcontext("Player 0, turn 1:"):
            game.select_combo(1)
            self.assertBalances(game, [0, 1])
            game.end_turn()
        with nullcontext("Player 1, turn 1:"):
            game.select_combo(0)
            self.assertBalances(game, [0, 2])
            game.end_turn()
        with nullcontext("Both players do nothing on turns 2-3:"):
            for _ in range(4):
                game.end_turn()
        self.assertEnded(game)
        self.assertBalances(game, [0, 2])

    def assertBalances(self, game: Game, expected: list[int]):
        """Check if all player balances match the `expected`."""
        actual = [p.coins for p in game.players]
        msg = "Player has incorrect amount of coins"
        self.assertListEqual(actual, expected, msg=msg)

    def assertEnded(self, game: Game):
        """Check if `game` is in end state and behaves correctly."""
        self.assertTrue(game.has_ended)
        with self.assertRaises(GameEnded):
            game.select_combo(0)
        with self.assertRaises(GameEnded):
            game.decline()
        with self.assertRaises(GameEnded):
            game.end_turn()
