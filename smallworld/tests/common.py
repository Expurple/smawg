'''Objects used by other modules in `smallworld.tests`.'''

import json
import unittest
from pathlib import Path

from smallworld.engine import Data


TESTS_DIR = Path(__file__).parent.resolve()
PACKAGE_DIR = TESTS_DIR.parent
REPO_DIR = PACKAGE_DIR.parent
EXAMPLES_DIR = Path(f"{REPO_DIR}/examples")


class BaseTest(unittest.TestCase):
    def load_data(self, filename: str) -> Data:
        with open(filename) as data_file:
            data_json = json.load(data_file)
        return Data(data_json)
