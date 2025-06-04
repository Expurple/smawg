# Changelog

All notable changes to this project will be documented in this file.

The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## \[Unreleased]

### Changed

- Updated the author's contact email.

## \[0.23.0] - 2024-03-03

### Added

- `TurnStage`, `Game.turn_stage` and `GameState.turn_stage` (rules already had
    to rely on the private version).
- `Player.is_owning(region)` helper method.

### Changed

- In asset files, `"has_a_lost_tribe": true` now must be set as
    `"symbols": ["Lost Tribe", ...]` instead.

## \[0.22.0] - 2023-11-16

### Added

- `--style=machine` option for `smawg play`.
- `show-turn` command for `smawg play`.

### Changed

- Autocompletion in `smawg play` became much smarter and appropriately suggests
    arguments, dry runs or dead ends instead of always suggesting commands.

## \[0.21.0] - 2023-09-30

### Added

- `smawg.basic_rules.Action` and its variants: `Decline`, `SelectCombo`,
    `Abandon`, `Conquer`, `ConquerWithDice`, `StartRedeployment`, `Deploy`,
    `EndTurn`.
- `smawg.default_rules.Action` (currently, it's the same as
    `smawg.basic_rules.Action`).
- `Game.do()` method as a single entry point for performing any `Action`.
- `AbstractRules.check()` method as a single entry point for checking any
        `Action`.
    - Its implementations in `smawg.basic_rules` and `smawg.default_rules`.

### Changed

- Error messages in `smawg play`.
- Rule plugins now must implement `AbstractRules.check()`.
- `AbstractRules` is now a `Generic` class, old code may not typecheck.

## \[0.20.0] - 2023-09-02

### Added

- `Map.adjacent` property.
- `smawg play` subcommand as the new recommended way to run `smawg.cli`.
- `smawg viz` subcommand as the new recommended way to run `smawg.viz`.

### Deprecated

- `smawg.cli` entry point in favor of `smawg play`.
- `smawg.viz` entry point in favor of `smawg viz`.

## \[0.19.0] - 2023-07-16

### Added

- `roll_dice()` convenience function.
- `Assets.shuffle()` convenience method.
- `Game.assets` and `GameState.assets` properties.

### Changed

- `Combo` is now a dataclass that's compared by value.
- `Game` no longer shuffles `assets` by default or provides a switch for this.
    If you need this functionality, use `Assets.shuffle()`.
- Maps are no longer allowed to contain "borders" between some tile and itself.

### Deprecated

- `Game.n_turns` and `GameState.n_turns`. Prefer `.assets.n_turns` instead.

### Removed

- Parameter `shuffle_data` of `Game.__init__()`. If you need this functionality,
    use `Assets.shuffle()`.

## \[0.18.0] - 2023-07-14

### Changed

- `smawg.viz --format=''` now acts as `--no-render`.
- Improvements in `smawg.viz` output:
    - Standard terrain types and symbols are now rendered in color.
    - Edges no longer overlap with nodes.
    - Large maps look more dense than before.
    - In generated labels, region symbols are now always sorted.
    - Generated labels now contain escaped newlines instead of raw newlines.

### Deprecated

- `smawg.viz --no-render` (use `--format=''` instead).

## \[0.17.0] - 2023-07-10

### Added

- `Region.symbols` field to support symbols like "Cavern", "Magic Source" and
    "Mine". This field is empty by default.
- Assets for the standard 2, 3, 4 and 5 player game setups.

### Changed

- `smawg.viz` now also displays `Region.symbols`.
- To reduce verbosity of map assets, `"has_a_lost_tribe"` and
    `"is_at_map_border"` are now optional and false by default.
- The minimum number of `races` and `abilities` in assets is lowered to
    `2*n_players` and `n_players` respectively. See the next change for
    reasons.
- The semantics of `n_selectable_combos` has changed. Previously, it required
    *exactly* `n_selectable_combos` at any moment:

    ```python
    assert len(game.combos) == n_selectable_combos
    ```

    But that rule is too strict. It doesn't even allow the standard 5 player
    setup, demanding to add a 15th race to the game.

    What we really care about is having at least 1 combo when the current
    player must pick a combo to proceed. In other situations, it's ok to have 0.
    And at any moment, there should be *no more than* `n_selectable_combos`:

    ```python
    if game.player.active_ability is None:
        assert 1 <= len(game.combos) <= n_selectable_combos
    else:
        assert len(game.combos) <= n_selectable_combos
    ```

    This should be enough to prevent stuck situations in common game
    configurations.

## \[0.16.0] - 2023-07-09

### Added

- Dependency on `pydantic`.
- Strongly typed `Map` and `Assets` objects.
- `Game.__init__()` overload that accepts `Assets` instead of `dict`.
- Package-level CLI entry point (`smawg`) with `schema` subcommand to generate
    JSON schema.

### Changed

- `GameState` constructor now accepts assets as `Assets` instead of `dict`.
- `validate()` and `Game.__init__()` now raise `pydantic.ValidationError`
    instead of `jsonschema.exceptions.ValidationError` or `smawg.InvalidAssets`.

### Deprecated

- Parameter `strict` of `validate()`.

### Removed

- Dependency on `jsonschema`.
- JSON schema in `smawg/assets_schema/` (now in can be autogenerated, see
    [README.md](./README.md#json-schema))
- `InvalidAssets` exception class (`pydantic.ValidationError` is used instead).

## \[0.15.0] - 2023-07-07

### Added

- `Game.owner_of()` and `GameState.owner_of()`.
- Exposed `Game.rules`, allowing to "dry run" an action and check if it's valid.
- Support for dry runs in `smawg.cli` ('?' operator).

### Changed

- Rule plugins now bound-check their arguments and yield `ValueError` instead
    of just assuming that they're valid.
- Updated instructions in `README.md` to use `venv`.

### Removed

- Support for Python 3.10.

### Fixed

- Typo in `docs/rules.md`.

## \[0.14.0] - 2023-07-02

### Added

- `is_in_redeployment_turn` property of `Game` and `GameState`.

### Changed

- `Game.conquer(..., use_dice=True)` now returns the value rolled on the dice.
- Documentation on game hooks now discourages their use.
    They may be deprecated in future versions.

### Fixed

- Required `flake8` plugins are now specified in `setup.cfg`.

## \[0.13.1] - 2022-12-30

### Fixed

- Typing in tests.
- Rules documentation not matching the test case.
- Broken file link in README.md.
- Unescaped square brackets in markdown.

## \[0.13.0] - 2022-11-15

### Added

- Effects from different terrain types:
    - Allow to start the conquests from a non-edge region
        whose shore is on a Sea adjacent to the edge of the board.
    - Conquering a Mountain now costs 1 additional token.
    - Conquering Seas and Lakes is now forbidden.
- `smawg.basic_rules` module where you can still find basic rules from v0.12.0.

### Changed

- `AbstractRules` now yield erros instead of raising.
- Pre-existing `RulesViolation` subclasses for basic rules should now be
    imported from `smawg.basic_rules` instead of `smawg.default_rules`.

## \[0.12.0] - 2022-09-04

### Added

- Support for custom rules:
    - `GameState` interface.
    - `AbstractRules` interface.
    - Reusable rule checker in `smawg.default_rules.Rules`.
    - `RulesT` parameter for `Game.__init__`.
    - `--rules` option for `smawg.cli`.
    - `docs/rules.md`

### Removed

- `smawg.exceptions` module. Instead,
    - import `InvalidAssets` and `RulesViolation` from `smawg`.
    - import detailed `RulesViolation` subclasses from `smawg.default_rules`.
- Misleading `RulesViolation.MESSAGE` attribute.

## \[0.11.1] - 2022-09-03

### Fixed

- `Combo.base_n_tokens` ignoring `Race.max_n_tokens`.

## \[0.11.0] - 2022-09-03

### Added

- Public symbols in `smawg`.

### Changed

- Examples in documentation to use imports from `smawg` directly.

### Removed

- `smawg.engine` (import `smawg` instead).
- `shuffle()` and `roll_dice()` that shouldn't have been public.
- Unused `Player.decline_ability`.

## \[0.10.0] - 2022-09-03

### Changed

- Constructors of `Ability`, `Race` and `Region`.
- Parameters of `validate()`.
- Speed up `Game` construction.
- JSON schema now rejects negative tile indexes in
    `assets["map"]["tile_borders"]`.
- `Game` constructor now validates tile borders, the number of races and the
    number of abilities, and may raise `InvalidAssets` exception.
- `assets/tiny.json` now contains more races to pass the checks.

### Removed

- `ABILITY_SCHEMA`, `RACE_SCHEMA`, `TILE_SCHEMA` and `ASSETS_SCHEMA`
    that shouldn't have been public.

### Fixed

- Unexpected crashes when assets contain too few races or abilities.
- Unexpected crashes when some map regions are not connected to the rest.
- Crashes or silent incorrect behaviour when map contains
    borders between non-existing tiles.

## \[0.9.1] - 2022-09-01

### Fixed

- Incorrect order of re-introducing races and abilities.

## \[0.9.0] - 2022-08-31

### Added

- `Game.regions` property.
- `terrain` property for regions (which doesn't affect anything yet).
- `validate()` function.
- `smawg.viz` utility.

### Changed

- Type annotations became stricter.

### Removed

- Support for Python 3.9.
- `smawg.VERSION` constant that shouldn't have been public.

### Fixed

- Code examples in documentation.
- Impossible requirement to deploy tokens from hand
    when the player has no regions and has already used the dice.

## \[0.8.0] - 2022-05-11

### Added

- `smawg.exceptions` module with new exception subtypes.

### Changed

- `RulesViolation` and `GameEnded` are moved to the new module.
- `smawg.engine` now throws more precise subtypes of `RulesViolation` instead
    of using it directly (but it still catches all cases as a base class).

## \[0.7.0] - 2022-05-01

### Added

- Lost Tribe tokens.

## \[0.6.0] - 2022-04-26

### Added

- The mechanic of abandoning regions.
- Related `Game` method: `abandon()`.
- Related `cli` command: `abandon`.

## \[0.5.0] - 2022-04-18

### Added

- Reinforcements dice mechanic.
- Related `Game.conquer()` argument: `use_dice`.
- Related `Game` hook: `"on_dice_rolled"`
- Related `cli` command: `conquer-dice`.

### Changed

- `cli` error messages when given wrong number of arguments.

## \[0.4.0] - 2022-04-12

### Added

- Optional redeployment step at the end of the turn.
- Related `Game` method: `start_redeployment()`.
- Related `cli` command: `redeploy`.

### Changed

- Default `Game()` arguments are now keyword-only.

## \[0.3.1] - 2022-02-11

### Added

- `py.typed` marker for PEP 561 compliance.

### Fixed

- Dates of releases in `CHANGELOG.md`.

## \[0.3.0] - 2022-02-01

### Added

- Explicit `"n_coins_on_start"` in assets
    (instead of implicitly deduced from `"n_combos"`).
- `Game.player` as a shortcut to `Game.players[Game.player_id]`.

### Changed

- In assets, replaced `"min_n_players"` and `"max_n_players"`
    with just `"n_players"`.
- Renamed `Game.current_player_id` to `Game.player_id`.

### Removed

- `n_players` parameter from `Game.__init__()`.
- `--players` option from `cli`.

## \[0.2.1] - 2022-02-01

### Fixed

- `Game` potentially breaking when `assets` are modified later.
- `cli` crashing when `show-regions` argument is out of bounds.
- "not enough values to unpack" when entering an empty line in `cli`.

## \[0.2.0] - 2022-02-01

### Added

- Schema and example of a `"map"` asset (without support for unique regions or
    Lost Tribes).
- The mechanic of conquering regions and earning coins, **but without**:
    - Reinforcements dice.
    - Redeployment at the end of the turn.
    - Ability to abandon regions.
- Related `Game` methods: `conquer()`, `deploy()`
- Related `Game` hook: `"on_redeploy"`
- Related `Player` attributes: `active_regions`, `decline_regions`,
    `tokens_on_hand`
- Related `cli` commands: `show-regions`, `conquer`, `deploy`.
- Column "Tokens on hand" for `cli` command `show-players`.

### Changed

- `select_combo()` now validates `combo_index` and raises `ValueError`.
- More useful error message when attempting to `decline()` while already in
    Decline.
- Tweaked `cli` error messages.

### Removed

- Dead code related to tokens (including empty "public" class `Token`).
- `Player` members that shouldn't have been public and got refactored out:
    - Methods `is_in_decline()` and `needs_to_pick_combo()`.
    - Attributes `acted_on_this_turn` and `declined_on_this_turn`.

## \[0.1.1] - 2022-01-25

### Fixed

- Validation of `"races"` and `"abilities"` objects in asset files.

## \[0.1.0] - 2022-01-24

### Added

- JSON schema for asset files.
- A minimal asset file, which specifies:
    - The number of players.
    - The number of available race+ability combos.
    - The number of turns.
    - A list of races.
    - A list of abilities.
- `smawg.engine` module with `Game` class, which provides:
    - Methods for picking a combo and entering Decline.
    - Properties for getting current stats.
    - A mechanism for setting hooks on game events:
        start of turn, end of turn, end of game.
- `smawg.cli` client app, which provides a text-based interface for the library.
- The ability to (sort of) play the game
    and lose if you don't pick the 0th combo!
