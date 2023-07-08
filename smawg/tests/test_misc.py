"""Tests that don't belong in other test modules."""

import json
import unittest
from typing import Any

from pydantic import ValidationError

from smawg import Ability, Combo, Race, validate
from smawg._metadata import ASSETS_DIR
from smawg.tests.common import TINY_ASSETS


class TestAssets(unittest.TestCase):
    """Tests for JSON files in `smawg/assets/`."""

    def test_assets(self) -> None:
        """Check if all files in `smawg/assets/` are valid and documented."""
        for file_name in ASSETS_DIR.glob("*.json"):
            with open(file_name) as assets_file:
                assets = json.load(assets_file)
            # Raises an error and fails the test if `assets` are invalid.
            validate(assets)


class TestCombo(unittest.TestCase):
    """Tests for `smawg._common.Combo` class."""

    def test_base_n_tokens(self) -> None:
        """Check if `base_n_tokens` respects `Race.max_n_tokens`."""
        race = Race("Some race", n_tokens=4, max_n_tokens=8)
        ability = Ability("Many", n_tokens=10)
        combo = Combo(race, ability)
        self.assertEqual(combo.base_n_tokens, 8)


class TestValidate(unittest.TestCase):
    """Tests for `smawg.validate()` function."""

    def test_invalid_assets(self) -> None:
        """Check if `validate()` raises an error on invalid assets."""
        invalid_fields: list[tuple[str, Any]] = [
            # Bad structure of nested objects:
            ("races", [{"not a": "race"}]),
            ("abilities", [{"not a": "ability"}]),
            ("map", {"not a": "map"}),
            # Borders between non-existring tiles:
            ("map", {
                "tiles": [],
                "tile_borders": [[-2, -1]]
            }),
            ("map", {
                "tiles": [],
                "tile_borders": [[2, 1]]
            }),
            # Impossible to achieve n_visible_combos=2:
            ("races", []),
            ("abilities", []),
        ]
        for key, value in invalid_fields:
            invalid_assets = {**TINY_ASSETS, key: value}
            with self.assertRaises(ValidationError):
                validate(invalid_assets)


if __name__ == "__main__":
    unittest.main()
