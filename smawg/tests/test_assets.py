"""Tests for JSON files in `smawg/assets/`."""

import json
import unittest

from smawg.engine import validate
from smawg._metadata import ASSETS_DIR


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


if __name__ == "__main__":
    unittest.main()
