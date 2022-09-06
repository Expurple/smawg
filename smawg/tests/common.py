"""Common objects for other `smawg.tests.*` modules."""

import json
from typing import Any

from smawg._metadata import ASSETS_DIR

__all__ = ["TINY_ASSETS"]


with open(f"{ASSETS_DIR}/tiny.json") as file:
    TINY_ASSETS: dict[str, Any] = json.load(file)
