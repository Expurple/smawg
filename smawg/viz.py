#!/usr/bin/env python3

"""Utility for visualizing maps from smawg asset files.

See https://github.com/expurple/smawg for more info about the project.
"""

import json
import sys
from argparse import ArgumentParser, Namespace
from typing import Any, Callable

from graphviz import Graph  # type:ignore

from smawg import validate
from smawg._metadata import PACKAGE_DIR, VERSION


DESCRIPTION = f"graphviz visualizer for smawg v{VERSION} maps"
VISIT_HOME_PAGE = "For more info, visit https://github.com/expurple/smawg"


def _do_nothing(*args: Any, **kwargs: Any) -> None:
    """Just accept any arguments and do nothing."""
    pass


def _parse_args() -> Namespace:
    """Parse and return command line arguments.

    On error, print usage and exit.
    """
    parser = ArgumentParser(description=DESCRIPTION, epilog=VISIT_HOME_PAGE)
    default_format = "png"
    parser.add_argument(
        "-f", "--format",
        metavar="FMT",
        default=default_format,
        help=f"the output file format (default: {default_format})",
    )
    parser.add_argument(
        "-v", "--view",
        action="store_true",
        help="open the output file after rendering"
    )
    parser.add_argument(
        "-n", "--no-render",
        action="store_true",
        help="generate a .gv file without rendering it (overrides --view)"
    )
    parser.add_argument(
        "-r", "--relative-path",
        action="store_true",
        help="search for ASSETS_FILE inside of smawg package directory"
    )
    parser.add_argument(
        "assets_file",
        metavar="ASSETS_FILE",
        help="path to JSON file with assets"
    )
    return parser.parse_args()


def build_graph(assets: dict[str, Any]) -> Graph:
    """Convert the map into a DOT representation, but don't render it yet."""
    validate(assets)
    map = assets["map"]
    graph = Graph(
        name="map",
        engine="sfdp",
        graph_attr={"overlap": "false"}
    )
    for i, tile in enumerate(map["tiles"]):
        node_attrs = {"label": f'{i}. {tile["terrain"]}'}
        if tile["has_a_lost_tribe"]:
            node_attrs["label"] += "\nLost Tribe"
        if tile["is_at_map_border"]:
            node_attrs["style"] = "bold"
        graph.node(str(i), **node_attrs)
    for tile1, tile2 in map["tile_borders"]:
        edge_attrs = {}
        if map["tiles"][tile1]["is_at_map_border"] \
                and map["tiles"][tile2]["is_at_map_border"]:
            edge_attrs["style"] = "bold"
        graph.edge(str(tile1), str(tile2), **edge_attrs)
    return graph


def save(graph: Graph, render_fmt: str | None = None, *, view: bool = False,
         on_save: Callable[[str], None] = _do_nothing) -> None:
    """Save the graph, optionally rendering it or opening the resulting file.

    For each saved file, fire `on_save` callback and pass a filename.
    """
    gv_file_name = graph.save()
    on_save(gv_file_name)
    if render_fmt is not None:
        rendered_file_name = graph.render(
            format=render_fmt, view=view, overwrite_source=False
        )
        on_save(rendered_file_name)


def _on_save(filename: str) -> None:
    print(f"smawg.viz: saved {repr(filename)}", file=sys.stderr)


if __name__ == "__main__":
    args = _parse_args()
    assets_file = args.assets_file
    if args.relative_path:
        assets_file = f"{PACKAGE_DIR}/{assets_file}"
    with open(assets_file) as file:
        assets = json.load(file)
    graph = build_graph(assets)
    format = None if args.no_render else args.format
    save(graph, format, view=args.view, on_save=_on_save)
