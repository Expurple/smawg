"""Tests for bundled CLI utilities."""

import subprocess
import unittest
from concurrent.futures import ThreadPoolExecutor

from smawg.basic_rules import (
    Abandon, Action, Conquer, ConquerWithDice, Decline, Deploy, EndTurn,
    SelectCombo, StartRedeployment
)
from smawg.cli import _MaybeDry, _parse_command


class TestMain(unittest.TestCase):
    """Tests for bundled CLI utilities."""

    def test_minimal_tasks(self) -> None:
        """Check if utilities can launch and complete minimal tasks."""
        commands = [
            ["python3", "-m", "smawg", "--help"],
            ["python3", "-m", "smawg", "schema"],
            ["python3", "-m", "smawg", "play", "--help"],
            ["python3", "-m", "smawg", "viz", "--help"],
            ["python3", "-m", "smawg.cli", "--help"],
            ["python3", "-m", "smawg.viz", "--help"],
        ]
        with ThreadPoolExecutor() as executor:
            for _ in executor.map(self.assert_completes_ok, commands):
                pass  # Re-raise the exception from that thread, if any.

    def assert_completes_ok(self, command: list[str]) -> None:
        """Check if `command` can run and exit with code 0 in 2 seconds.

        If it can't, an exception is raised and the test is failed.
        """
        subprocess.run(command, capture_output=True, check=True, timeout=2)


def _dry(action: Action) -> _MaybeDry:
    return _MaybeDry(dry_run=True, action=action)


class TestCliParseCommand(unittest.TestCase):
    """Tests for `smawg.cli._parse_command()`.

    That function is private, but having tests helps with fearless refactoring.
    """

    def test_empty_line(self) -> None:
        """The function should return None for empty and whitespace lines."""
        self.assertEqual(_parse_command(""), None)
        self.assertEqual(_parse_command("  "), None)

    def test_unknown_command(self) -> None:
        """The function should raise ValueError on unknown commands."""
        self.assertRaises(ValueError, _parse_command, "foo")
        self.assertRaises(ValueError, _parse_command, "bar")

    def test_question_mark_spaces(self) -> None:
        """Spaces before and after the question mark should not matter."""
        self.assertEqual(_parse_command("?decline"), _dry(Decline()))
        self.assertEqual(_parse_command("? decline"), _dry(Decline()))
        self.assertEqual(_parse_command(" ?decline"), _dry(Decline()))
        self.assertEqual(_parse_command(" ? decline"), _dry(Decline()))

    def test_valid_dry_run(self) -> None:
        """These commands should support dry runs."""
        self.assertEqual(_parse_command("?combo 0"), _dry(SelectCombo(0)))
        self.assertEqual(_parse_command("?abandon 0"), _dry(Abandon(0)))
        self.assertEqual(_parse_command("?conquer 0"), _dry(Conquer(0)))
        self.assertEqual(
            _parse_command("?conquer-dice 0"), _dry(ConquerWithDice(0))
        )
        self.assertEqual(_parse_command("?deploy 1 0"), _dry(Deploy(1, 0)))
        self.assertEqual(
            _parse_command("?redeploy"), _dry(StartRedeployment())
        )
        self.assertEqual(_parse_command("?decline"), _dry(Decline()))
        self.assertEqual(_parse_command("?end-turn"), _dry(EndTurn()))

    def test_unsupported_dry_run(self) -> None:
        """These commands should not support dry runs."""
        self.assertRaises(ValueError, _parse_command, "?help")
        self.assertRaises(ValueError, _parse_command, "?quit")
        self.assertRaises(ValueError, _parse_command, "?show-combos")
        self.assertRaises(ValueError, _parse_command, "?show-players")
        self.assertRaises(ValueError, _parse_command, "?show-regions 0")


if __name__ == "__main__":
    unittest.main()
