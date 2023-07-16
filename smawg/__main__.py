#!/usr/bin/env python3

"""The main CLI entry point of smawg.

See https://github.com/expurple/smawg for more info about the project.
"""

import json
from argparse import ArgumentParser, Namespace

from pydantic import TypeAdapter

import smawg.cli as cli
import smawg.viz as viz
from smawg import Assets
from smawg._metadata import VERSION


VISIT_HOME_PAGE = "For more info, visit https://github.com/expurple/smawg"


def _parse_args() -> Namespace:
    """Parse and return command line arguments.

    On error, print usage and exit.
    """
    parser = ArgumentParser(
        "smawg",
        description=f"smawg {VERSION}, "
                    "free implementation of Small World board game.",
        epilog=VISIT_HOME_PAGE,
    )
    subparsers = parser.add_subparsers(
        dest="subcommand",
        help="(see --help of each for more details)",
        metavar="SUBCOMMAND",
        required=True,
    )
    play_parser = cli.argument_parser()
    subparsers.add_parser(
        "play",
        help="play the game through a CLI",
        parents=[play_parser],
        conflict_handler="resolve",
        # For some reason, these aren't automatically inherited from `parents`:
        description=play_parser.description,
        epilog=play_parser.epilog
    )
    SCHEMA_DESCRIPTION =\
        f"generate and print JSON schema for smawg {VERSION} assets"
    subparsers.add_parser(
        "schema",
        description=SCHEMA_DESCRIPTION,
        epilog=VISIT_HOME_PAGE,
        help="generate and print JSON schema for assets",
    )
    viz_parser = viz.argument_parser()
    subparsers.add_parser(
        "viz",
        help="vizualize game maps using graphviz",
        parents=[viz_parser],
        conflict_handler="resolve",
        # For some reason, these aren't automatically inherited from `parents`:
        description=viz_parser.description,
        epilog=viz_parser.epilog
    )
    return parser.parse_args()


def _main() -> None:
    args = _parse_args()
    match args.subcommand:
        case "play":
            cli.root_command(args)
        case "schema":
            schema = TypeAdapter(Assets).json_schema()
            print(json.dumps(schema, indent=2))
        case "viz":
            viz.root_command(args)
        case _:
            assert False, "all commands should be handled"


if __name__ == "__main__":
    _main()
