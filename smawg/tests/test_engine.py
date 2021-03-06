"""Tests for `smawg.engine` module.

This module can also be seen as a collection of usage examples.
"""

import inspect
import json
import unittest
from copy import deepcopy
from contextlib import AbstractContextManager, nullcontext
from typing import Any, Callable, Optional

import jsonschema.exceptions

import smawg.exceptions as exc
from smawg import _ASSETS_DIR
from smawg.engine import Ability, Game, Race


TINY_ASSETS: dict[str, Any] = {}


def setUpModule() -> None:
    """Preload game assets only once and only when running the tests."""
    global TINY_ASSETS
    with open(f"{_ASSETS_DIR}/tiny.json") as file:
        TINY_ASSETS = json.load(file)


class TestAbility(unittest.TestCase):
    """Tests for `smawg.engine.Ability` class."""

    def test_valid_json(self) -> None:
        """Check if `Ability.__init__` propetly parses the given json."""
        ability = Ability({"name": "Some Name", "n_tokens": 4})
        self.assertEqual(ability.name, "Some Name")
        self.assertEqual(ability.n_tokens, 4)

    def test_invalid_jsons(self) -> None:
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

    def assertInvalid(self, json: dict[str, Any]) -> None:
        """Check if `Ability.__init__` raises when given this `json`."""
        with self.assertRaises(jsonschema.exceptions.ValidationError):
            _ = Ability(json)


class TestRace(unittest.TestCase):
    """Tests for `smawg.engine.Race` class."""

    INVALID_JSONS: list[dict[str, Any]] = [
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

    def test_valid_json(self) -> None:
        """Check if `Race.__init__` propetly parses the given json."""
        race = Race({"name": "Some Name", "n_tokens": 4, "max_n_tokens": 9})
        self.assertEqual(race.name, "Some Name")
        self.assertEqual(race.n_tokens, 4)
        self.assertEqual(race.max_n_tokens, 9)

    def test_invalid_jsons(self) -> None:
        """Check if `Race.__init__` raises when given invalid jsons."""
        for j in TestRace.INVALID_JSONS:
            self.assertInvalid(j)

    def assertInvalid(self, json: dict[str, Any]) -> None:
        """Check if `Race.__init__` raises when given this `json`."""
        with self.assertRaises(jsonschema.exceptions.ValidationError):
            _ = Race(json)


class TestGame(unittest.TestCase):
    """General tests for `smawg.engine.Game` class.

    Tests for hooks and particular methods
    are extracted into separate test fixtures.
    """

    def test_game_end(self) -> None:
        """Run a full game and then check if it's in end state."""
        game = Game(TINY_ASSETS, shuffle_data=False)
        with nullcontext("Player 0, turn 1:"):
            game.select_combo(1)
            game.conquer(0)
            game.conquer(1)
            game.conquer(2)
            game.end_turn()
        with nullcontext("Player 1, turn 1:"):
            game.select_combo(0)
            game.conquer(3)
            game.conquer(0)
            game.end_turn()
        with nullcontext("Both players do nothing on turns 2-3:"):
            for _ in range(2):
                game.deploy(game.player.tokens_on_hand, 1)
                game.end_turn()
                game.deploy(game.player.tokens_on_hand, 3)
                game.end_turn()
        self.assertEnded(game)

    def test_redeployment_pseudo_turn(self) -> None:
        """Check if redeployment pseudo-turn works as expected."""
        assets = {**TINY_ASSETS, "n_players": 3}
        game = Game(assets, shuffle_data=False)
        with nullcontext("Player 0, turn 1:"):
            game.select_combo(0)
            game.conquer(0)
            game.conquer(1)
            game.conquer(2)
            game.end_turn()
        with nullcontext("Player 1, turn 1:"):
            game.select_combo(0)
            game.conquer(3)
            game.conquer(0)  # Region owned by player 0.
            game.end_turn()
        with nullcontext("Player 0 redeploys tokens:"):
            self.assertEqual(game.player_id, 0)
            self.assertEqual(game.player.tokens_on_hand, 2)
            with self.assertRaises(exc.ForbiddenDuringRedeployment):
                game.select_combo(0)
            with self.assertRaises(exc.ForbiddenDuringRedeployment):
                game.abandon(1)
            with self.assertRaises(exc.ForbiddenDuringRedeployment):
                game.conquer(4)
            with self.assertRaises(exc.ForbiddenDuringRedeployment):
                game.decline()
            with self.assertRaises(exc.UndeployedTokens):
                game.end_turn()
            game.deploy(game.player.tokens_on_hand, 1)
            game.end_turn()
        with nullcontext("Player 2, turn 1:"):
            self.assertEqual(game.current_turn, 1)
            self.assertEqual(game.player_id, 2)

    def test_coin_rewards(self) -> None:
        """Check if coin rewards work as expected."""
        game = Game(TINY_ASSETS, shuffle_data=False)
        self.assertBalances(game, [1, 1])  # Initial coin balances
        with nullcontext("Player 0, turn 1:"):
            game.select_combo(1)
            self.assertBalances(game, [0, 1])  # Paid 1 coin for combo 1
            game.conquer(0)
            game.conquer(1)
            game.conquer(2)
            game.end_turn()
        self.assertBalances(game, [3, 1])  # Reward for active regions
        with nullcontext("Player 1, turn 1:"):
            game.select_combo(0)
            self.assertBalances(game, [3, 2])  # Combo 0 had coin from player 0
            game.conquer(3)
            game.conquer(0)
            game.end_turn()
        self.assertBalances(game, [3, 4])  # Reward for active regions
        with nullcontext("Player 0, turn 2:"):
            game.decline()
            game.end_turn()
        self.assertBalances(game, [5, 4])  # Reward for decline regions 1 and 2

    def assertBalances(self, game: Game, expected: list[int]) -> None:
        """Check if all player balances match the `expected`."""
        actual = [p.coins for p in game.players]
        msg = "Player has incorrect amount of coins"
        self.assertListEqual(actual, expected, msg=msg)

    def assertEnded(self, game: Game) -> None:
        """Check if `game` is in end state and all methods raise GameEnded."""
        self.assertTrue(game.has_ended)
        with self.assertRaises(exc.GameEnded):
            game.select_combo(0)
        with self.assertRaises(exc.GameEnded):
            game.decline()
        with self.assertRaises(exc.GameEnded):
            game.abandon(0)
        with self.assertRaises(exc.GameEnded):
            game.conquer(0)
        with self.assertRaises(exc.GameEnded):
            game.start_redeployment()
        with self.assertRaises(exc.GameEnded):
            game.deploy(1, 0)
        with self.assertRaises(exc.GameEnded):
            game.end_turn()


class TestGameHooks(unittest.TestCase):
    """Tests for `Game` hooks."""

    def setUp(self) -> None:
        """Declare an internal attribute that underlies `assertFiresHook()`."""
        self._hook_has_fired = False

    def test_on_turn_start(self) -> None:
        """Check if `"on_turn_start"` hook fires when expected."""
        assets = {**TINY_ASSETS, "n_players": 3}
        with self.assertFiresHook():
            game = Game(assets, shuffle_data=False,
                        hooks={"on_turn_start": self.default_hook_handler()})
        game.select_combo(0)
        game.conquer(0)
        game.conquer(1)
        game.conquer(2)
        with self.assertFiresHook():
            game.end_turn()

    def test_on_dice_rolled(self) -> None:
        """Check if `"on_dice_rolled"` hook fires with proper arguments."""
        def on_dice_rolled(game: Game, value: int,
                           conquest_success: bool) -> None:
            self.assertEqual(value, 2)
            self.assertEqual(conquest_success, True)
            self._hook_has_fired = True

        assets = {**TINY_ASSETS, "n_players": 3}
        game = Game(assets, shuffle_data=False, dice_roll_func=lambda: 2,
                    hooks={"on_dice_rolled": on_dice_rolled})
        game.select_combo(0)
        with self.assertFiresHook():
            game.conquer(0, use_dice=True)

    def test_on_turn_end(self) -> None:
        """Check if `"on_turn_end"` hook fires when expected."""
        assets = {**TINY_ASSETS, "n_players": 3}
        game = Game(assets, shuffle_data=False,
                    hooks={"on_turn_end": self.default_hook_handler()})
        game.select_combo(0)
        game.conquer(0)
        game.deploy(game.player.tokens_on_hand, 0)
        with self.assertFiresHook():
            game.end_turn()

    def test_on_redeploy(self) -> None:
        """Check if `"on_redeploy"` hook fires when expected."""
        assets = {**TINY_ASSETS, "n_players": 3}
        game = Game(assets, shuffle_data=False,
                    hooks={"on_redeploy": self.default_hook_handler()})
        with nullcontext("Player 0, turn 1:"):
            game.select_combo(0)
            game.conquer(0)
            game.conquer(1)
            game.conquer(2)
            game.end_turn()
        with nullcontext("Player 1, turn 1:"):
            game.select_combo(0)
            game.conquer(3)
            game.conquer(0)  # Region owned by player 0.
            with self.assertFiresHook():
                game.end_turn()

    def test_on_game_end(self) -> None:
        """Check if `"on_game_end"` hook fires when expected."""
        game = Game(TINY_ASSETS, shuffle_data=False,
                    hooks={"on_game_end": self.default_hook_handler()})
        with nullcontext("Player 0, turn 1:"):
            game.select_combo(1)
            game.conquer(0)
            game.conquer(1)
            game.conquer(2)
            game.end_turn()
        with nullcontext("Player 1, turn 1:"):
            game.select_combo(0)
            game.conquer(3)
            game.conquer(0)
            game.end_turn()
        with nullcontext("Both players do nothing on turns 2-3:"):
            game.deploy(game.player.tokens_on_hand, 1)
            game.end_turn()
            game.deploy(game.player.tokens_on_hand, 3)
            game.end_turn()
            game.deploy(game.player.tokens_on_hand, 1)
            game.end_turn()
            game.deploy(game.player.tokens_on_hand, 3)
            with self.assertFiresHook():
                game.end_turn()

    def default_hook_handler(self) -> Callable[[Game], None]:
        """Return a simple hook handler that makes `assertFiresHook()` work."""
        def handler(game: Game) -> None:
            self._hook_has_fired = True
        return handler

    def assertFiresHook(self) -> AbstractContextManager[Any]:
        """Assert that a `Game` hook is fired inside of the wrapped block.

        Depends on an appropriate handler that sets `_hook_has_fired` to `True`
        """
        test_case = self

        class AssertFiresHook:
            def __enter__(self) -> "AssertFiresHook":
                test_case._hook_has_fired = False
                return self

            def __exit__(self, *_: Any) -> None:
                if not test_case._hook_has_fired:
                    msg = "Expected a Game hook to be executed, but it wasn't"
                    test_case.fail(msg)
                test_case._hook_has_fired = False

        return AssertFiresHook()


class TestGameDecline(unittest.TestCase):
    """Tests for `smawg.engine.Game.decline()` method."""

    def test_exceptions(self) -> None:
        """Check if the method raises expected exceptions.

        This doesn't include `GameEnded`, which is tested separately for
        convenience.
        """
        assets = {**TINY_ASSETS, "n_players": 1}
        game = Game(assets, shuffle_data=False)
        with nullcontext("Player 0, turn 1:"):
            with self.assertRaises(exc.NoActiveRace):
                game.decline()
            game.select_combo(0)
            with self.assertRaises(exc.DecliningWhenActive):
                game.decline()  # Just got a new race during this turn.
            game.conquer(0)
            game.deploy(game.player.tokens_on_hand, 0)
            game.end_turn()
        with nullcontext("Player 0, turn 2:"):
            game.conquer(1)
            with self.assertRaises(exc.DecliningWhenActive):
                game.decline()  # Already used the active race during this turn
            game.deploy(game.player.tokens_on_hand, 1)
            game.end_turn()
        with nullcontext("Player 0, turn 3:"):
            game.decline()
            with self.assertRaises(exc.NoActiveRace):
                game.decline()  # Already in decline


class TestGameSelectCombo(unittest.TestCase):
    """Tests for `smawg.engine.Game.select_combo()` method."""

    def test_exceptions(self) -> None:
        """Check if the method raises expected exceptions.

        This doesn't include `GameEnded`, which is tested separately for
        convenience.
        """
        assets = {**TINY_ASSETS, "n_players": 1, "n_coins_on_start": 0}
        game = Game(assets, shuffle_data=False)
        with nullcontext("Player 0, turn 1:"):
            for combo in [-10, -1, len(game.combos), 999]:
                # "combo_index must be between 0 and {len(game.combos)}"
                with self.assertRaises(ValueError):
                    game.select_combo(combo)
            with self.assertRaises(exc.NotEnoughCoins):
                game.select_combo(1)
            game.select_combo(0)
            with self.assertRaises(exc.SelectingWhenActive):
                game.select_combo(0)
            game.conquer(0)
            game.deploy(game.player.tokens_on_hand, 0)
            game.end_turn()
        with nullcontext("Player 0, turn 2:"):
            game.decline()
            with self.assertRaises(exc.SelectingOnDeclineTurn):
                game.select_combo(0)


class TestGameAbandon(unittest.TestCase):
    """Tests for `smawg.engine.Game.abandon()` method."""

    def test_functionality(self) -> None:
        """Check if the method behaves as expected when used correctly."""
        assets = {**TINY_ASSETS, "n_players": 1}
        game = Game(assets, shuffle_data=False)
        with nullcontext("Player 0, turn 1:"):
            game.select_combo(0)
            game.conquer(0)
            game.conquer(1)
            game.conquer(2)
            game.end_turn()
        with nullcontext("Player 0, turn 2:"):
            self.assertEqual(game.player.active_regions, {0: 1, 1: 1, 2: 1})
            self.assertEqual(game.player.tokens_on_hand, 6)
            game.abandon(0)
            self.assertEqual(game.player.active_regions, {1: 1, 2: 1})
            self.assertEqual(game.player.tokens_on_hand, 7)

    def test_exceptions(self) -> None:
        """Check if the method raises expected exceptions.

        This doesn't include `GameEnded`, which is tested separately for
        convenience.
        """
        assets = {**TINY_ASSETS, "n_players": 1}
        game = Game(assets, shuffle_data=False)
        with nullcontext("Player 0, turn 1:"):
            with self.assertRaises(exc.NoActiveRace):
                game.abandon(0)
            game.select_combo(0)
            with self.assertRaises(exc.NonControlledRegion):
                game.abandon(0)
            game.conquer(0)
            with self.assertRaises(exc.AbandoningAfterConquests):
                game.abandon(0)
            for region in [-1, len(TINY_ASSETS["map"]["tiles"]), 99]:
                # "region must be between 0 and {len(assets["map"]["tiles"])}"
                with self.assertRaises(ValueError):
                    game.abandon(region)
            game.deploy(game.player.tokens_on_hand, 0)
            game.end_turn()
        with nullcontext("Player 0, turn 2:"):
            game.start_redeployment()
            with self.assertRaises(exc.ForbiddenDuringRedeployment):
                game.abandon(0)


class TestGameConquer(unittest.TestCase):
    """Tests for `smawg.engine.Game.conquer()` method."""

    def test_diceless_functionality(self) -> None:
        """Check if the method behaves as expected with `use_dice=False`."""
        game = Game(TINY_ASSETS, shuffle_data=False)
        with nullcontext("Player 0, turn 1:"):
            game.select_combo(1)
            with self.assertConquers(0, cost=3):
                game.conquer(0)
            with self.assertConquers(1, cost=3):
                game.conquer(1)
            with self.assertConquers(2, cost=3):
                game.conquer(2)
            game.end_turn()
        with nullcontext("Player 1, turn 1:"):
            game.select_combo(0)
            with self.assertConquers(3, cost=3):
                game.conquer(3)
            with self.assertConquers(0, cost=6):
                game.conquer(0)
            self.assertEqual(game.players[0].tokens_on_hand, 2)
            self.assertEqual(game.players[0].active_regions, {1: 3, 2: 3})

    def test_dice_win(self) -> None:
        """Common victory cases with `use_dice=True`."""
        assets = {**TINY_ASSETS, "n_players": 1}
        game = Game(assets, shuffle_data=False, dice_roll_func=lambda: 1)
        with nullcontext("Player 0, turn 1:"):
            # The dice isn't necessary and results in using less tokens:
            game.select_combo(0)
            with self.assertConquers(0, cost=2):
                game.conquer(0, use_dice=True)
            game.deploy(game.player.tokens_on_hand, 0)
            game.end_turn()
        with nullcontext("Player 0, turn 2:"):
            # The dice is necessary, all tokens are used:
            game.deploy(game.player.tokens_on_hand - 2, 0)
            with self.assertConquers(1, cost=2):
                game.conquer(1, use_dice=True)

    def test_dice_rolled_3_when_needed_3(self) -> None:
        """1 token should be put on a region."""
        game = Game(TINY_ASSETS, shuffle_data=False, dice_roll_func=lambda: 3)
        game.select_combo(0)
        with self.assertConquers(0, cost=1):
            game.conquer(0, use_dice=True)

    def test_dice_fail(self) -> None:
        """Check if conquest fails when given insufficient dice value."""
        game = Game(TINY_ASSETS, shuffle_data=False, dice_roll_func=lambda: 1)
        game.select_combo(0)
        game.conquer(0)
        game.deploy(game.player.tokens_on_hand - 1, 0)  # Leave 1 in hand.
        game.conquer(1, use_dice=True)  # Needs to roll at least 2, but gets 1.
        self.assertNotIn(1, game.player.active_regions)
        self.assertEqual(game.player.tokens_on_hand, 1)

    def test_lost_tribe(self) -> None:
        """Test on regions with Lost Tribes."""
        assets = deepcopy(TINY_ASSETS)
        assets["map"]["tiles"][0]["has_a_lost_tribe"] = True
        assets["n_players"] = 1
        game = Game(assets, shuffle_data=False)
        with nullcontext("Player 0, turn 1:"):
            game.select_combo(0)
            # Conquest should require 4 tokens instead of 3.
            with self.assertConquers(0, cost=4):
                game.conquer(0)
            game.deploy(game.player.tokens_on_hand, 0)
            game.end_turn()
        with nullcontext("Player 0, turn 2:"):
            # After the region is conquested,
            # the Lost Tribe shouldn't be there anymore.
            # If we abandon the region, conquest should cost 3 tokens.
            game.abandon(0)
            with self.assertConquers(0, cost=3):
                game.conquer(0)

    def test_after_abandoning_all_regions(self) -> None:
        """Test the unlikely case where the player has abandoned all regions.

        Conquests should work in the same way
        as if the player has just chosen a new race.
        """
        assets = {**TINY_ASSETS, "n_players": 1}
        game = Game(assets, shuffle_data=False)
        with nullcontext("Player 0, turn 1:"):
            game.select_combo(0)
            game.conquer(0)
            game.deploy(game.player.tokens_on_hand, 0)
            game.end_turn()
        with nullcontext("Player 0, turn 2:"):
            game.abandon(0)
            # If the player didn't abandon region 0, region 2 would be
            # available to be conquered, because it's adjacent.
            # But now he must start from the edge of the map.
            with self.assertRaises(exc.NotAtBorder):
                game.conquer(2)
            # Region 4 isn't adjacent to region 0,
            # but it's at the edge of the map, which is what we need right now.
            with self.assertConquers(4, cost=3):
                game.conquer(4)

    def test_common_exceptions(self) -> None:
        """Check if the method raises expected exceptions on common checks.

        This doesn't include `GameEnded`, which is tested separately for
        convenience.
        """
        assets = {**TINY_ASSETS, "n_players": 1}
        game = Game(assets, shuffle_data=False)
        with nullcontext("Player 0, turn 1:"):
            with self.assertRaises(exc.NoActiveRace):
                game.conquer(0)  # Attempt to conquer without an active race.
            game.select_combo(0)
            for region in [-1, len(TINY_ASSETS["map"]["tiles"]), 99]:
                # "region must be between 0 and {len(assets["map"]["tiles"])}"
                with self.assertRaises(ValueError):
                    game.conquer(region)
            with self.assertRaises(exc.NotAtBorder):
                game.conquer(2)
            game.conquer(0)
            with self.assertRaises(exc.ConqueringOwnRegion):
                game.conquer(0)
            with self.assertRaises(exc.NonAdjacentRegion):
                game.conquer(4)
            game.start_redeployment()
            with self.assertRaises(exc.ForbiddenDuringRedeployment):
                game.conquer(3)
            game.deploy(game.player.tokens_on_hand, 0)
            game.end_turn()
        with nullcontext("Player 1, turn 1:"):
            game.conquer(1, use_dice=True)
            with self.assertRaises(exc.AlreadyUsedDice):
                game.conquer(2)

    def test_diceless_exceptions(self) -> None:
        """Check if method raises exceptions specific to `use_dice=False`."""
        game = Game(TINY_ASSETS, shuffle_data=False)
        game.select_combo(0)
        game.conquer(0)
        game.deploy(game.player.tokens_on_hand - 2, 0)
        with self.assertRaises(exc.NotEnoughTokensToConquer):  # Need 3, have 2
            game.conquer(1)

    def test_dice_only_exceptions(self) -> None:
        """Check if method raises exceptions specific to `use_dice=True`."""
        game = Game(TINY_ASSETS, shuffle_data=False)
        with nullcontext("Player 0, turn 1:"):
            game.select_combo(0)
            game.conquer(0)
            game.conquer(1)
            game.conquer(2)
            with self.assertRaises(exc.RollingWithoutTokens):
                game.conquer(3, use_dice=True)
            game.end_turn()
        with nullcontext("Player 1, turn 1:"):
            game.select_combo(0)
            game.conquer(3)
            game.deploy(game.player.tokens_on_hand, 3)
            game.end_turn()
        with nullcontext("Player 0, turn 2:"):
            # Player 0 has 6 tokens on hand.
            # Player 1 has 9 tokens in region 3.
            # 12 tokens are needed to conquer it, which is more than 6+3.
            with self.assertRaises(exc.NotEnoughTokensToRoll):
                game.conquer(3, use_dice=True)

    def assertConquers(self, region: int, *, cost: Optional[int] = None
                       ) -> AbstractContextManager[Any]:
        """Assert that the `region` is conquered inside of the wrapped block.

        When `cost` is specified,
        also assert that `cost` amount of tokens is used.
        """
        test = self
        # Dark magic to implicitly get it from the calling test method.
        game: Game = inspect.stack()[1][0].f_locals["game"]

        class AssertConquers:
            def __enter__(self) -> "AssertConquers":
                self._tokens_before = game.player.tokens_on_hand
                return self

            def __exit__(self, *_: Any) -> None:
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


class TestGameStartRedeployment(unittest.TestCase):
    """Tests for `smawg.engine.Game.start_redeployment()` method."""

    def test_functionality(self) -> None:
        """Check if the method behaves as expected when used correctly."""
        assets = {**TINY_ASSETS, "n_players": 1}
        game = Game(assets, shuffle_data=False)
        game.select_combo(0)
        TOKENS_TOTAL = game.player.tokens_on_hand
        game.conquer(0)
        game.conquer(1)
        self.assertDictEqual(game.player.active_regions, {0: 3, 1: 3})
        self.assertEqual(game.player.tokens_on_hand, TOKENS_TOTAL - 6)
        game.start_redeployment()
        self.assertDictEqual(game.player.active_regions, {0: 1, 1: 1})
        self.assertEqual(game.player.tokens_on_hand, TOKENS_TOTAL - 2)

    def test_exceptions(self) -> None:
        """Check if the method raises expected exceptions.

        This doesn't include `GameEnded`, which is tested separately for
        convenience.
        """
        assets = {**TINY_ASSETS, "n_players": 1}
        game = Game(assets, shuffle_data=False)
        with nullcontext("Player 0, turn 1:"):
            with self.assertRaises(exc.NoActiveRace):
                game.start_redeployment()
            game.select_combo(0)
            with self.assertRaises(exc.NoActiveRegions):
                game.start_redeployment()
            game.conquer(0)
            game.start_redeployment()
            game.deploy(game.player.tokens_on_hand, 0)
            with self.assertRaises(exc.ForbiddenDuringRedeployment):
                game.start_redeployment()
            game.end_turn()
        with nullcontext("Player 0, turn 2:"):
            game.decline()
            with self.assertRaises(exc.NoActiveRace):
                game.start_redeployment()


class TestGameDeploy(unittest.TestCase):
    """Tests for `smawg.engine.Game.deploy()` method."""

    def test_functionality(self) -> None:
        """Check if the method behaves as expected when used correctly."""
        game = Game(TINY_ASSETS, shuffle_data=False)
        game.select_combo(0)
        TOKENS_TOTAL = game.player.tokens_on_hand
        game.conquer(0)
        self.assertEqual(game.player.tokens_on_hand, TOKENS_TOTAL - 3)
        self.assertEqual(game.player.active_regions, {0: 3})
        game.deploy(game.player.tokens_on_hand, 0)
        self.assertEqual(game.player.tokens_on_hand, 0)
        self.assertEqual(game.player.active_regions, {0: TOKENS_TOTAL})

    def test_exceptions(self) -> None:
        """Check if the method raises expected exceptions.

        This doesn't include `GameEnded`, which is tested separately for
        convenience.
        """
        game = Game(TINY_ASSETS, shuffle_data=False)
        with self.assertRaises(exc.NoActiveRace):
            game.deploy(1, 0)
        game.select_combo(0)
        with self.assertRaises(exc.NonControlledRegion):
            game.deploy(1, 0)
        game.conquer(0)
        with self.assertRaises(exc.NotEnoughTokensToDeploy):
            game.deploy(game.player.tokens_on_hand + 1, 0)
        # "n_tokens must be greater then 0"
        for n_tokens in [-99, -1, 0]:
            with self.assertRaises(ValueError):
                game.deploy(n_tokens, 0)
        # "region must be between 0 and {len(assets["map"]["tiles"])}"
        for region in [-10, -1, len(TINY_ASSETS["map"]["tiles"]), 99]:
            with self.assertRaises(ValueError):
                game.deploy(1, region)


class TestGameEndTurn(unittest.TestCase):
    """Tests for `smawg.engine.Game.end_turn()` method."""

    def test_exceptions(self) -> None:
        """Check if the method raises expected exceptions.

        This doesn't include `GameEnded`, which is tested separately for
        convenience.
        """
        game = Game(TINY_ASSETS, shuffle_data=False)
        with self.assertRaises(exc.EndBeforeSelect):
            game.end_turn()
        game.select_combo(0)
        with self.assertRaises(exc.UndeployedTokens):
            game.end_turn()
