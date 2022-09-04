"""Tests for `smawg.common` module."""

import unittest

from smawg.common import Ability, Combo, Race


class TestCombo(unittest.TestCase):
    """Tests for `smawg.common.Combo` class."""

    def test_base_n_tokens(self) -> None:
        """Check if `base_n_tokens` respects `Race.max_n_tokens`."""
        race = Race("Some race", n_tokens=4, max_n_tokens=8)
        ability = Ability("Many", n_tokens=10)
        combo = Combo(race, ability)
        self.assertEqual(combo.base_n_tokens, 8)


if __name__ == "__main__":
    unittest.main()
