# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added
- Schema and example of a `"map"` asset.

## [0.1.1] - 2021-01-25
### Fixed
- Validation of `"races"` and `"abilities"` objects in asset files.

## [0.1.0] - 2021-01-24
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