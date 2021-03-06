# Changelog
All notable changes to this project will be documented in this file.

The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added
- `Game.regions` property.
- `terrain` property for regions (which doesn't affect anything yet).

### Changed
- Type annotations became stricter.

### Removed
- Support for Python 3.9.

### Fixed
- Code examples in documentation.

## [0.8.0] - 2022-05-11
### Added
- `smawg.exceptions` module with new exception subtypes.

### Changed
- `RulesViolation` and `GameEnded` are moved to the new module.
- `smawg.engine` now throws more precise subtypes of `RulesViolation` instead
    of using it directly (but it still catches all cases as a base class).

## [0.7.0] - 2022-05-01
### Added
- Lost Tribe tokens.

## [0.6.0] - 2022-04-26
### Added
- The mechanic of abandoning regions.
- Related `Game` method: `abandon()`.
- Related `cli` command: `abandon`.

## [0.5.0] - 2022-04-18
### Added
- Reinforcements dice mechanic.
- Related `Game.conquer()` argument: `use_dice`.
- Related `Game` hook: `"on_dice_rolled"`
- Related `cli` command: `conquer-dice`.

### Changed
- `cli` error messages when given wrong number of arguments.

## [0.4.0] - 2022-04-12
### Added
- Optional redeployment step at the end of the turn.
- Related `Game` method: `start_redeployment()`.
- Related `cli` command: `redeploy`.

### Changed
- Default `Game()` arguments are now keyword-only.

## [0.3.1] - 2022-02-11
### Added
- `py.typed` marker for PEP 561 compliance.

### Fixed
- Dates of releases in `CHANGELOG.md`.

## [0.3.0] - 2022-02-01
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

## [0.2.1] - 2022-02-01
### Fixed
- `Game` potentially breaking when `assets` are modified later.
- `cli` crashing when `show-regions` argument is out of bounds.
- "not enough values to unpack" when entering an empty line in `cli`.

## [0.2.0] - 2022-02-01
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

## [0.1.1] - 2022-01-25
### Fixed
- Validation of `"races"` and `"abilities"` objects in asset files.

## [0.1.0] - 2022-01-24
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
