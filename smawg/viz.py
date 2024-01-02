#!/usr/bin/env python3

"""Utility for visualizing maps from smawg asset files.

Running this module directly is deprecated, run it using `smawg viz`.

See https://github.com/expurple/smawg for more info about the project.
"""

import json
import sys
from argparse import ArgumentParser, Namespace, RawDescriptionHelpFormatter

from graphviz import Graph  # type:ignore
from pydantic import TypeAdapter

from smawg import Assets, Map
from smawg._metadata import PACKAGE_DIR, VERSION


__all__ = ["argument_parser", "root_command"]


def argument_parser() -> ArgumentParser:
    """Configure and create a command line argument parser."""
    parser = ArgumentParser(
        description=f"Vizualize smawg {VERSION} maps using graphviz.\n\n"
                    "Creates two files: map.gv and map.gv.FMT "
                    "(the rendered image).",
        epilog="For more info, visit https://github.com/expurple/smawg",
        formatter_class=RawDescriptionHelpFormatter
    )
    default_format = "png"
    parser.add_argument(
        "-f", "--format",
        metavar="FMT",
        default=default_format,
        help=f"image format (don't render if empty; default: {default_format})"
    )
    parser.add_argument(
        "-n", "--no-render",
        action="store_true",
        help="deprecated alias to --format=''"
    )
    parser.add_argument(
        "-v", "--view",
        action="store_true",
        help="open the image after rendering"
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
    return parser


_TERRAIN_COLORS = {
    "Farmland": "gold",
    "Forest": "green3",
    "Hill": "lightgreen",
    "Lake": "deepskyblue",
    "Mountain": "azure2",
    "Sea": "deepskyblue",
    "Swamp": "chocolate2"
}
_MARKED_SYMBOLS = {
    "Cavern": "⬛ Cavern",
    "Lost Tribe": "⬜ Lost Tribe",
    "Magic Source": "🟦 Magic Source",
    "Mine": "🟥 Mine",
}


def _build_graph(map: Map) -> Graph:
    """Convert the map into a DOT representation, but don't render it yet."""
    graph = Graph(
        name="map",
        engine="sfdp",
        graph_attr={
            "overlap": "false", "overlap_scaling": "2", "splines": "spline"
        }
    )
    for i, tile in enumerate(map.tiles):
        node_attrs = {"label": f"{i}. {tile.terrain}"}
        style_items = list[str]()
        for symbol in sorted(tile.symbols):
            node_attrs["label"] += f"\\n{_MARKED_SYMBOLS.get(symbol, symbol)}"
        if tile.is_at_map_border:
            style_items.append("bold")
        color = _TERRAIN_COLORS.get(tile.terrain, None)
        if color is not None:
            style_items.append("filled")
            node_attrs["fillcolor"] = color
        if len(style_items) > 0:
            node_attrs["style"] = ",".join(style_items)
        graph.node(str(i), **node_attrs)
    for tile1, tile2 in map.tile_borders:
        edge_attrs = {}
        if map.tiles[tile1].is_at_map_border \
                and map.tiles[tile2].is_at_map_border:
            edge_attrs["style"] = "bold"
        graph.edge(str(tile1), str(tile2), **edge_attrs)
    return graph


def root_command(args: Namespace) -> None:
    """The function that is run after parsing the command line arguments."""
    assets_file = args.assets_file
    if args.relative_path:
        assets_file = f"{PACKAGE_DIR}/{assets_file}"
    with open(assets_file) as file:
        assets_dict = json.load(file)
    assets: Assets = TypeAdapter(Assets).validate_python(assets_dict)
    graph = _build_graph(assets.map)
    gv_file_name = graph.save()
    print(f"smawg: saved {repr(gv_file_name)}", file=sys.stderr)
    format = "" if args.no_render else args.format
    if format != "":
        rendered_file_name = graph.render(
            format=format, view=args.view, overwrite_source=False
        )
        print(f"smawg: saved {repr(rendered_file_name)}", file=sys.stderr)


def _main() -> None:
    """The entry point of `smawg.viz` command.

    Deprecated in favor of `smawg viz`.
    """
    parser = argument_parser()
    assert isinstance(parser.description, str), "type narrowing for mypy"
    parser.description += "\n\nTHIS ENTRY POINT IS DEPRECATED, " \
                          "launch as 'python3 -m smawg viz' instead."
    parser.formatter_class = RawDescriptionHelpFormatter
    args = parser.parse_args()
    root_command(args)


if __name__ == "__main__":
    _main()
