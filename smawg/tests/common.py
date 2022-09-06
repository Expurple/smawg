"""Common objects for other `smawg.tests.*` modules."""

import json
import unittest
from contextlib import AbstractContextManager
from typing import Any

import smawg.basic_rules as br
from smawg import Game
from smawg._metadata import ASSETS_DIR

__all__ = ["BaseGameTest", "TINY_ASSETS"]


with open(f"{ASSETS_DIR}/tiny.json") as file:
    TINY_ASSETS: dict[str, Any] = json.load(file)


class BaseGameTest(unittest.TestCase):
    """Defines useful assertions for testing `smawg.Game`."""

    def assertBalances(self, game: Game, expected: list[int]) -> None:
        """Check if all player balances match the `expected`."""
        actual = [p.coins for p in game.players]
        msg = "Player has an incorrect amount of coins"
        self.assertEqual(actual, expected, msg=msg)

    def assertConquers(self, game: Game, region: int, *,
                       cost: int | None = None) -> AbstractContextManager[Any]:
        """Assert that the `region` is conquered inside of the context.

        When `cost` is specified,
        also assert that `cost` amount of tokens is used.
        """
        test = self

        class AssertConquers:
            def __enter__(self) -> "AssertConquers":
                self._tokens_before = game.player.tokens_on_hand
                return self

            def __exit__(self, exc_type: Any, exc_value: Any, tb: Any) -> None:
                if exc_value is not None:
                    return  # Propagate the exception.
                msg = "Expected a successfull conquest"
                test.assertIn(region, game.player.active_regions, msg=msg)
                if cost is not None:
                    msg = "Conquest is using an unexpected amount of tokens"
                    tokens_in_region = game.player.active_regions[region]
                    test.assertEqual(tokens_in_region, cost, msg=msg)
                    delta_tokens_in_hand = \
                        self._tokens_before - game.player.tokens_on_hand
                    test.assertEqual(delta_tokens_in_hand, cost, msg=msg)

        return AssertConquers()

    def assertEnded(self, game: Game) -> None:
        """Check if `game` is in end state and all methods raise GameEnded."""
        self.assertTrue(game.has_ended)
        with self.assertRaises(br.GameEnded):
            game.select_combo(0)
        with self.assertRaises(br.GameEnded):
            game.decline()
        with self.assertRaises(br.GameEnded):
            game.abandon(0)
        with self.assertRaises(br.GameEnded):
            game.conquer(0)
        with self.assertRaises(br.GameEnded):
            game.start_redeployment()
        with self.assertRaises(br.GameEnded):
            game.deploy(1, 0)
        with self.assertRaises(br.GameEnded):
            game.end_turn()
