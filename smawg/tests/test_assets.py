"""Tests for JSON files in `smawg/assets/`."""

import json
import unittest

import jsonschema.exceptions

from smawg.engine import validate
from smawg._metadata import ASSETS_DIR


class TestAssets(unittest.TestCase):
    """Tests for JSON files in `smawg/assets/`."""

    def test_against_schema(self) -> None:
        """Test all asset files against `smawg/assets_schema/assets.json`."""
        for assets_file_name in ASSETS_DIR.glob("*.json"):
            with open(assets_file_name) as assets_file:
                assets_json = json.load(assets_file)
            # Raises an error and fails the test
            # if `assets_json` is invalid or contains undocumented keys.
            validate(assets_json, strict=True)


class TestSchemaValidation(unittest.TestCase):
    """Meta-tests for `smawg/assets_schema/` and the validation process."""

    def test_invalid_nested_objects(self) -> None:
        """Test if invalid nested objects fail to match against nested schemas.

        Prevents a category of bugs where `TestAssets` passes on invalid assets
        because the schema or the validation process is incorrect.
        """
        invalid_values = [
            ("races", [{"not a": "race"}]),
            ("abilities", [{"not a": "ability"}]),
            ("map", [{"not a": "map"}])
        ]
        with open(f"{ASSETS_DIR}/tiny.json") as assets_file:
            assets = json.load(assets_file)
        for key, value in invalid_values:
            invalid_assets = {**assets, key: value}
            with self.assertRaises(jsonschema.exceptions.ValidationError):
                validate(invalid_assets)


if __name__ == "__main__":
    unittest.main()
