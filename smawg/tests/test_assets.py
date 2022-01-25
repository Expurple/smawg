"""Tests for JSON files in `smawg/assets/`."""

import json
import unittest
from copy import deepcopy

import jsonschema
import jsonschema.exceptions

from smawg import _ASSETS_DIR
from smawg.engine import ASSETS_SCHEMA, _JS_REF_RESOLVER


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
            jsonschema.validate(assets_json, strict_schema,
                                resolver=_JS_REF_RESOLVER)


class TestSchemaValidation(unittest.TestCase):
    """Meta-tests for `smawg/assets_schema/` and the validation process."""

    def test_invalid_nested_objects(self):
        """Test if invalid nested objects fail to match against nested schemas.

        Prevents a category of bugs where `TestAssets` passes on invalid assets
        because the schema or the validation process is incorrect.
        """
        invalid_values = [
            ("races", [{"not a": "race"}]),
            ("abilities", [{"not a": "ability"}]),
            ("map", [{"not a": "map"}])
        ]
        with open(f"{_ASSETS_DIR}/tiny.json") as assets_file:
            assets = json.load(assets_file)
        for key, value in invalid_values:
            invalid_assets = deepcopy(assets)
            invalid_assets[key] = value
            with self.assertRaises(jsonschema.exceptions.ValidationError):
                jsonschema.validate(invalid_assets, ASSETS_SCHEMA,
                                    resolver=_JS_REF_RESOLVER)
