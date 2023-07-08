"""Various metadata that `smawg` package needs to know about itself at runtime.

See https://github.com/expurple/smawg for more info about the project.
"""

import importlib.metadata
from configparser import ConfigParser
from pathlib import Path


PACKAGE_DIR = Path(__file__).parent.resolve()
"""Path to the currently used `smawg` package."""

ASSETS_DIR = Path(f"{PACKAGE_DIR}/assets")
"""Path to `assets/` directory in the currently used `smawg` package."""

VERSION: str
"""The version of `smawg` package as an `"x.y.z"` format string."""

try:
    # This will work if the package is installed (e.g. with `setup.py`, `pip`).
    VERSION = importlib.metadata.version("smawg")
except importlib.metadata.PackageNotFoundError:
    # If `smawg` is not installed,
    # Assume that we're in a repo and try to fall back on local `setup.cfg`:
    repo_dir = PACKAGE_DIR.parent
    cfg = ConfigParser()
    cfg.read(f"{repo_dir}/setup.cfg")
    VERSION = cfg["metadata"]["version"]
    # Clean up namespace
    del repo_dir, cfg


# Clean up namespace
del ConfigParser, importlib, Path
