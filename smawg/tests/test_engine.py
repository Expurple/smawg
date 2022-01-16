"""Tests for `smawg.engine` module.

This module can also be seen as a collection of usage examples.
"""

import json
import unittest
from contextlib import nullcontext

import jsonschema.exceptions

from smawg import _ASSETS_DIR
from smawg.engine import Ability, Game, GameEnded, Race


class TestAbility(unittest.TestCase):
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
        self.assertInvalid({"n_tokens": 4})
        # Missing "n_tokens"
        self.assertInvalid({"name": "Some Name"})
        # Invalid type of "n_tokens"
        self.assertInvalid({"name": "Some Name", "n_tokens": None})
        self.assertInvalid({"name": "Some Name", "n_tokens": 4.5})
        self.assertInvalid({"name": "Some Name", "n_tokens": "4"})
        # Invalid value of "n_tokens"
        self.assertInvalid({"name": "Some Name", "n_tokens": -4})

    def assertInvalid(self, json: dict):
        """Check if `Ability.__init__` raises when given this `json`."""
        with self.assertRaises(jsonschema.exceptions.ValidationError):
            _ = Ability(json)


class TestRace(unittest.TestCase):
    """Tests for `smawg.engine.Race` class."""

    INVALID_JSONS = [
        # Missing required properties
        {"random keys": "and values"},
        {},
        {"n_tokens": 4, "max_n_tokens": 9},
        {"name": "Some Name", "max_n_tokens": 9},
        {"name": "Some Name", "n_tokens": 4},
        # Invalid types
        {"name": None, "n_tokens": 4, "max_n_tokens": 9},
        {"name": "Some Name", "n_tokens": 4.5, "max_n_tokens": 9},
        {"name": "Some Name", "n_tokens": 4, "max_n_tokens": None},
        # Invalid values
        {"name": "Some Name", "n_tokens": -4, "max_n_tokens": 9},
        {"name": "Some Name", "n_tokens": 4, "max_n_tokens": -9}
    ]

    def test_valid_json(self):
        """Check if `Race.__init__` propetly parses the given json."""
        race = Race({"name": "Some Name", "n_tokens": 4, "max_n_tokens": 9})
        self.assertEqual(race.name, "Some Name")
        self.assertEqual(race.n_tokens, 4)
        self.assertEqual(race.max_n_tokens, 9)

    def test_invalid_jsons(self):
        """Check if `Race.__init__` raises when given invalid jsons."""
        for j in TestRace.INVALID_JSONS:
            self.assertInvalid(j)

    def assertInvalid(self, json: dict):
        """Check if `Race.__init__` raises when given this `json`."""
        with self.assertRaises(jsonschema.exceptions.ValidationError):
            _ = Race(json)


class TestGame(unittest.TestCase):
    """Tests for `smawg.engine.Game` class."""

    def test_tiny_game_scenario(self):
        """Run a full game based on `tiny.json` and check every step."""
        with open(f"{_ASSETS_DIR}/tiny.json") as file:
            assets = json.load(file)
        game = Game(assets, n_players=2)
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
