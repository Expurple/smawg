"""Tests that don't belong in other test modules."""

import json
import unittest
from typing import Any

from pydantic import TypeAdapter, ValidationError

from smawg import Ability, Assets, Combo, Race, validate
from smawg._metadata import ASSETS_DIR
from smawg.tests.common import TINY_ASSETS


class TestAssets(unittest.TestCase):
    """Tests for JSON files in `smawg/assets/`."""

    def test_assets(self) -> None:
        """Check if all files in `smawg/assets/` are valid."""
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

    def test_eq(self) -> None:
        """Combos should be compared by value."""
        race = Race("Example", n_tokens=5, max_n_tokens=15)
        ability = Ability("Example", n_tokens=5)
        combo1 = Combo(race, ability)
        combo2 = Combo(race, ability)
        self.assertEqual(combo1, combo2)


class TestValidate(unittest.TestCase):
    """Tests for `smawg.validate()` function.

    These mostly make sure that invalid assets always raise
    `pydantic.ValidationError` and never other exceptions like `TypeError`.
    """

    def test_non_dict_assets(self) -> None:
        """Check if `validate()` raises `ValidationError` on non-dict assets.

        When loading assets from an external JSON file,
        this can happen and our dict type hint can't prevent this.
        """
        invalid_assets: Any
        for invalid_assets in [None, True, 123, "abc", []]:
            with self.assertRaises(ValidationError):
                validate(invalid_assets)

    def test_missing_fields(self) -> None:
        """Check if `validate()` raises `ValidationError` on missing fields."""
        schema = TypeAdapter(Assets).json_schema()
        required_fields: list[str] = schema["required"]
        for field in required_fields:
            invalid_assets = {**TINY_ASSETS}
            del invalid_assets[field]
            with self.assertRaises(ValidationError):
                validate(invalid_assets)

    def test_invalid_fields(self) -> None:
        """Check if `validate()` raises `ValidationError` on invalid fields."""
        invalid_fields: list[tuple[str, Any]] = [
            # Flat values in place of arrays/objects:
            ("races", False),
            ("races", ["not a race"]),
            ("abilities", 0),
            ("abilities", [{"not a ability"}]),
            ("map", "not a map"),
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
            # Tile shares a border with itself:
            ("map", {
                "tiles": [{"terrain": "Forest"}],
                "tile_borders": [[0, 0]]
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
