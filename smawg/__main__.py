#!/usr/bin/env python3

"""The main CLI entry point of smawg.

See https://github.com/expurple/smawg for more info about the project.
"""

import json
from argparse import ArgumentParser, Namespace

from pydantic.json_schema import GenerateJsonSchema

from smawg import Assets
from smawg._metadata import VERSION


VISIT_HOME_PAGE = "For more info, visit https://github.com/expurple/smawg"


def _parse_args() -> Namespace:
    """Parse and return command line arguments.

    On error, print usage and exit.
    """
    parser = ArgumentParser(
        "smawg",
        description=f"smawg {VERSION}",
        epilog=VISIT_HOME_PAGE,
    )
    subparsers = parser.add_subparsers(
        dest="subcommand",
        help="(see --help of each for more details)",
        metavar="SUBCOMMAND",
        required=True,
    )
    SCHEMA_DESCRIPTION =\
        f"generate and print JSON schema for smawg {VERSION} assets"
    subparsers.add_parser(
        "schema",
        description=SCHEMA_DESCRIPTION,
        epilog=VISIT_HOME_PAGE,
        help="generate and print JSON schema for assets",
    )
    return parser.parse_args()


def _command_schema() -> None:
    assets_schema = Assets.__pydantic_core_schema__  # type:ignore
    assets_json_schema = GenerateJsonSchema().generate(assets_schema)
    print(json.dumps(assets_json_schema, indent=2))


def _main() -> None:
    args = _parse_args()
    match args.subcommand:
        case "schema":
            _command_schema()
        case _:
            assert False, "all commands should be handled"


if __name__ == "__main__":
    _main()
