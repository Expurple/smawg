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
* Support for custom maps, races and other assets.
* Deterministic or randomized outcomes.

### **Missing features** (in progress):

* Different region types (Seas, Mountains, etc).
* Unique Race and Special Power abilities.

### Future plans:

* Options for more machine-readable CLI output.
* In-house AI and GUI examples.
* Support for plugins with new ability types ???


# Releases

See [CHANGELOG.md](./CHANGELOG.md)


# Requirements

* Python 3.9+ (currently, only 3.9 is tested)
* [jsonschema](https://github.com/Julian/jsonschema)
* [tabulate](https://github.com/astanin/python-tabulate)


# Installation

* `git clone https://github.com/Expurple/smawg.git`
* `cd smawg/`
* `pip install --user .`


# Assets

`smawg` usually gets static assets (like a list of races) from a JSON file.

Currently, the only available set of assets is
[smawg/assets/tiny.json](smawg/assets/tiny.json).

You can create and use your own asset files.
You're not required to contribute them back, but I would appreciate it.

For documentation, see the JSON schema in
[smawg/assets_schema/assets.json](smawg/assets_schema/assets.json).

The schema doesn't specify a visual layout for game maps.
I imagine the map from `tiny.json` as `1)`, but it may be as well represented
as something like `2)` or `3)` and it will still work properly,
because functionally it's the same map:
```
    1)               2)               3)
+-------+        +-------+        +--------+
| 0 | 1 |        | 1 ^ 0 |        | 4 |  3 |
|   ^   |        |  / \  |        |   ^    |
|  / \  |        |-< 2 >-|        |  / \   |
|-< 2 >-|        |  \ /  |        |-< 2 >--|
|  \ /  |        |   v   |        |  \ /   |
|   v   |        | 4 | 3 |        |   v    |
| 3 | 4 |        |   |   |        | 1 |  0 |
+-------+        +-------+        +--------+
```


# Usage

## As a CLI app

Generally, it's invoked as
* `python3 -m smawg.cli`

A simple example set of options would be
* `python3 -m smawg.cli --relative-path assets/tiny.json`

It should guide you through the usage.

## As a library

```python
import json

# If you're dealing with (possibly invalid) user input,
# you might want to also import `RulesViolation` for catching it.
from smawg.engine import Game


# If you want, you can directly construct `assets` dict
# instead of reading from file.
with open('some/path/to/assets.json') as assets_file:
    assets = json.load(assets_file)

# Provide additional arguments or set hooks on game events, if needed.
# See `docs/hooks.md` for more info about hooks.
game = Game(assets)

# Call `game` methods to perform actions.
# Read `game` properties to monitor the game state.
# See `help(Game)` for more info.
```

You can also find "real world" usage examples in
[cli.py](./smawg/cli.py) and [test_engine.py](./smawg/tests/test_engine.py)


# Contributing

Feel free to open a
[Github issue](https://github.com/Expurple/smawg/issues/new/choose)
or contact me personally.

If you wish to participate in development, this should get you started:
* Fork this repo on Github.
* `git clone git@github.com:YOUR-USERNAME/smawg.git`
* `cd smawg/`
* `pip install --user .[dev]`
* `bin/add-pre-commit-hook.sh`

Any contributions are welcome, but [missing featues](##Features:) and
[open issues](https://github.com/Expurple/smawg/issues) should be prioritized.

Before submitting a pull request, please test and document your changes.

## Tests

Can be run using the standard library's
* `python3 -m unittest discover smawg/tests/`
* or any other test runner that supports `unittest` format.


# Contacts

* **Home page** - [smawg](https://github.com/expurple/smawg)

* **Author** - Dmitry Alexandrov <adk230@yandex.ru\>


# License

Copyright (c) 2022 Dmitry Alexandrov.

Licensed under [GPL v.3 or later](./LICENSE)

This copyright only applies to the code and other documents in this repository,
**not** the concept, title or any other property of the original game.
