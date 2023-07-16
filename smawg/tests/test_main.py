"""Tests for bundled CLI utilities."""

import subprocess
import unittest
from concurrent.futures import ThreadPoolExecutor


class TestMain(unittest.TestCase):
    """Tests for bundled CLI utilities."""

    def test_minimal_tasks(self) -> None:
        """Check if utilities can launch and complete minimal tasks."""
        commands = [
            ["python3", "-m", "smawg", "--help"],
            ["python3", "-m", "smawg", "schema"],
            ["python3", "-m", "smawg", "play", "--help"],
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


if __name__ == "__main__":
    unittest.main()
