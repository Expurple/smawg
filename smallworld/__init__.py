"""Backend engine for Small World board game.

See https://github.com/expurple/smallworld for more info.
"""

from pathlib import Path


_PACKAGE_DIR = Path(__file__).parent.resolve()
"""Path to `smallworld` package.

This in an **unreliable** helper for development and testing.

If you've a user and installed `smallworld` through `pip` or `setup.py`,
you should use this instead:
```
import sysconfig
smallworld_package_dir = sysconfig.get_path("smallworld")
```
"""

_REPO_DIR = _PACKAGE_DIR.parent
"""Path to checked out `smallworld` repository.

This in an **unreliable** helper for development and testing.
It only works correctly if you execute/import modules
from a local `smallworld` repository.

If you've installed `smallworld` through `pip` or `setup.py`,
you shouldn't use this.
"""

_EXAMPLES_DIR = Path(f"{_REPO_DIR}/examples")
"""Path to `examples/` directory in checked out `smallworld` repository.

This in an **unreliable** helper for development and testing.
It only works correctly if you execute/import modules
from a local `smallworld` repository.

If you've installed `smallworld` through `pip` or `setup.py`,
you shouldn't use this.
"""

# Clean up namespace
del Path
