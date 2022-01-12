"""Objects used by other modules in `smawg.tests`."""

import json
import unittest

from smawg.engine import Data


class BaseTest(unittest.TestCase):
    """Common functionality for `Test*` classes."""

    def load_data(self, filename: str) -> Data:
        """Open `filename`, parse `Data` object from json and return it."""
        with open(filename) as data_file:
            data_json = json.load(data_file)
        return Data(data_json)
