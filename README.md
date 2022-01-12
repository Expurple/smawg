# smawg

Python backend for
[Small World](https://en.m.wikipedia.org/wiki/Small_World_(board_game))
board game,
designed for writing third-party AIs and clients around it.

It has a bundled CLI client for interactive use
and easy interoperability with other programming languages.

## Features:

* High level API for performing in-game actions and getting current stats.
    * Imperatively or by setting hooks on game events.
* Automatic maintainance of game state (manages tokens, calculates score, etc).
* Automatic checks for violation of the rules.
* Support for custom maps, races, powers and other constants/resources.
* Deterministic or randomized outcomes.

### **Missing essential features** (in progress):

* A lot of core concepts: maps, attacking, redeploying, rewarding...
* Implementation of unique race abilities.

### Future plans:

* More tests, better documentation for code and JSONs.
* JSONs with full sets of races and abilities, original maps, etc.
* Options for more machine-readable CLI output.
* In-house AI and GUI examples.
* Support for plugins with new ability types ???


# Requirements

* Python 3.9+ (currently, only 3.9 is tested)
* [tabulate](https://github.com/astanin/python-tabulate) (for `smawg.cli`)


# Installation

* `git clone https://github.com/Expurple/smawg.git`
* `cd smawg/`
* `pip install --user .`


# Usage

## As a CLI app

Generally, it's invoked as
* `python3 -m smawg.cli`

A simple example set of options would be
* `python3 -m smawg.cli --players=2 examples/tiny_data.json`

It should guide you through the usage.

## As a library, imperative-style

```python
import json

from smawg.engine import Data, Game


# If you want, you can directly construct `data_json` dict
# instead of reading from file.
with open('some/path/to/data.json') as data_file:
    data_json = json.load(data_file)

data = Data(data_json)

# Provide different arguments, if needed.
game = Game(data, n_players=2)
# Call `game` methods to perform actions.
# Read `game` properties to monitor the game state.
# See `help(Game)` for more info.
```

You can also find a "real world" example in [cli.py](./smawg/cli.py)

## As a library, hooks-style

Refer to [docs/hooks.md](./docs/hooks.md)


# Testing

Tests in [smawg/tests/](smawg/tests)
use the standard `unittest` module.

You can run them by executing
* `python3 -m unittest discover`
* or any other test runner that supports `unittest` format.


# Contributing

Any contributions are welcome, but [missing featues](##Features) should be
prioritized.

Before submitting, please make sure that:
* Your code uses type hinting.
* `mypy --config-file= smawg/` doesn't report any errors.
* `flake8 --isolated smawg/` doesn't report any errors (with
    [flake8-docstrings](https://pypi.org/project/flake8-docstrings/) installed).
* New features are tested.
* All tests pass.

The easiest way to do that is to configure a pre-commit hook.

On *nix systems, you can do that by executing `bin/add-pre-commit-hook.sh`


# Contacts

* **Home page** - [smawg](https://github.com/expurple/smawg)

* **Author** - Dmitry Alexandrov <adk230@yandex.ru\>


# Licence

Copyright (c) 2022 Dmitry Alexandrov.

Licensed under [GPL v.3](./LICENSE)

This copyright only applies to the code and other documents in this repository,
**not** the concept, title or any other property of the original game.
