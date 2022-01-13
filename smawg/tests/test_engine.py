"""Tests for `smawg.engine` module."""

from contextlib import nullcontext

from smawg import _EXAMPLES_DIR
from smawg.engine import Game, GameEnded
from smawg.tests.common import BaseTest


class TestGame(BaseTest):
    """Tests for `smawg.engine.Game` class."""

    def test_tiny_game_scenario(self):
        """Run a full game based on `tiny_game.json` and check every step."""
        tiny_data = self.load_data(f"{_EXAMPLES_DIR}/tiny_data.json")
        game = Game(tiny_data, n_players=2)
        self.assertBalances(game, [1, 1])
        with nullcontext("Player 0, turn 0:"):
            game.select_combo(1)
            self.assertBalances(game, [0, 1])
            game.end_turn()
        with nullcontext("Player 1, turn 0:"):
            game.select_combo(0)
            self.assertBalances(game, [0, 2])
            game.end_turn()
        with nullcontext("Both players do nothing on turns 1-2:"):
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
