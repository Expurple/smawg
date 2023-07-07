# smawg

Python backend for
[Small World](https://en.m.wikipedia.org/wiki/Small_World_(board_game))
board game,
designed for writing third-party AIs and clients around it.

It has a bundled CLI client for interactive use
and easy interoperability with other programming languages.

## Features

* High level API for performing in-game actions and getting current stats.
    * Imperatively or by setting hooks on game events.
* Automatic maintainance of game state (manages tokens, calculates score, etc).
* Automatic checks for violation of the rules.
    * The rule checker is exposed, so you can also "dry run" an action to check
    if it's valid.
* Support for custom maps, races and other assets.
* Support for custom rules (see [docs/rules.md](docs/rules.md)).
* Deterministic or randomized outcomes.

### Missing features (in progress)

* Unique effects for each Race and Special Power.

### Future plans

* Options for more machine-readable CLI output.
* In-house AI and GUI examples.

## Releases

See [CHANGELOG.md](./CHANGELOG.md)

## Requirements

* Python 3.11+ (currently, only 3.11 is tested)
* [jsonschema](https://github.com/Julian/jsonschema)
* [tabulate](https://github.com/astanin/python-tabulate) (only for `smawg.cli`)
* [graphviz](https://github.com/xflr6/graphviz) (only for `smawg.viz`)

## Installation

User wide install if your OS allows it:

```sh
git clone https://github.com/Expurple/smawg.git
cd smawg/
pip install --user .
```

Or install into `venv`:

```sh
git clone https://github.com/Expurple/smawg.git
cd smawg/
python3 -m venv venv
source venv/bin/activate
pip install .
```

## Assets

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

```text
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

To easily reason about your maps, you can use `smawg.viz` utility.
Typical usage:

```bash
python3 -m smawg.viz --view some/path/to/assets.json
```

## Usage

### As a CLI app

Generally, it's invoked as

```bash
python3 -m smawg.cli
```

A simple example set of options would be

```bash
python3 -m smawg.cli --relative-path assets/tiny.json
```

It should guide you through the usage.

### As a library

```python
import json

from smawg import Game
# If you're dealing with (possibly invalid) user input:
from smawg import RulesViolation


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
[smawg/cli.py](./smawg/cli.py) and [smawg/tests/](./smawg/tests/)

## Contributing

Feel free to open a
[Github issue](https://github.com/Expurple/smawg/issues/new/choose)
or contact me personally.

If you wish to participate in development, this should get you started:

```sh
# <Fork this repo on Github>
git clone git@github.com:YOUR-USERNAME/smawg.git
cd smawg/
python3 -m venv venv
source venv/bin/activate
pip install .[dev] && pip uninstall smawg # Install only dependencies
bin/add-pre-commit-hook.sh
```

Any contributions are welcome, but [missing featues](#features) and
[open issues](https://github.com/Expurple/smawg/issues) should be prioritized.

Before submitting a pull request, please test and document your changes.

Tests can be run using

* the standard library's `python3 -m unittest discover smawg/tests/`
* or any other test runner that supports `unittest` format.

## Contacts

* **Home page** - [smawg](https://github.com/expurple/smawg)
* **Author** - Dmitrii Aleksandrov <adk230@yandex.ru\>

## License

Copyright (c) 2022 Dmitrii Aleksandrov.

Licensed under [GPL v.3 or later](./LICENSE)

This copyright only applies to the code and other documents in this repository,
**not** the concept, title or any other property of the original game.
