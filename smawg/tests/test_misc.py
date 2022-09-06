"""Tests that don't belong in other test modules."""

import json
import unittest

from jsonschema.exceptions import ValidationError

from smawg import Ability, Combo, InvalidAssets, Race, validate
from smawg._metadata import ASSETS_DIR
from smawg.tests.common import TINY_ASSETS


class TestAssets(unittest.TestCase):
    """Tests for JSON files in `smawg/assets/`."""

    def test_assets(self) -> None:
        """Check if all files in `smawg/assets/` are valid and documented."""
        for file_name in ASSETS_DIR.glob("*.json"):
            with open(file_name) as assets_file:
                assets = json.load(assets_file)
            # Raises an error and fails the test
            # if `assets_json` is invalid or contains undocumented keys.
            validate(assets, strict=True)


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
        invalid_fields = [
            # Bad structure of nested objects:
            (ValidationError, "races", [{"not a": "race"}]),
            (ValidationError, "abilities", [{"not a": "ability"}]),
            (ValidationError, "map", {"not a": "map"}),
            # Borders between non-existring tiles:
            (ValidationError, "map", {
                "tiles": [],
                "tile_borders": [[-2, -1]]
            }),
            (InvalidAssets, "map", {
                "tiles": [],
                "tile_borders": [[2, 1]]
            }),
            # Impossible to achieve n_visible_combos=2:
            (InvalidAssets, "races", []),
            (InvalidAssets, "abilities", []),
        ]
        for exc_type, key, value in invalid_fields:
            invalid_assets = {**TINY_ASSETS, key: value}
            with self.assertRaises(exc_type):
                validate(invalid_assets)


if __name__ == "__main__":
    unittest.main()
