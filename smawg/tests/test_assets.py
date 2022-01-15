"""Tests for JSON files in `smawg/assets/`."""

import json
import unittest
from copy import deepcopy

import jsonschema

from smawg import _ASSETS_DIR
from smawg.engine import ASSETS_SCHEMA


class TestAssets(unittest.TestCase):
    """Tests for JSON files in `smawg/assets/`."""

    def test_against_schema(self):
        """Test all asset files against `smawg/assets_schema/assets.json`."""
        # Fail on keys which are not documented in the schema.
        # This is useful if I commit new keys and forget to document.
        strict_schema = deepcopy(ASSETS_SCHEMA)
        strict_schema["additionalProperties"] = False

        for assets_file_name in _ASSETS_DIR.glob("*.json"):
            with open(assets_file_name) as assets_file:
                assets_json = json.load(assets_file)
            # Fails the test if `ValidationError` is raised.
            jsonschema.validate(assets_json, strict_schema)
