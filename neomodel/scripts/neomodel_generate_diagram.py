"""
.. _neomodel_generate_diagram:

``neomodel_generate_diagram``
-----------------------------

::

    usage: _neomodel_generate_diagram [-h] [--file-type <arrows|puml>] [--write-to-dir <someapp/diagrams> ...]
    
    Connects to a Neo4j database and inspects existing nodes and relationships.
    Infers the schema of the database and generates Python class definitions.

    If a connection URL is not specified, the tool will look up the environment 
    variable NEO4J_BOLT_URL. If that environment variable is not set, the tool
    will attempt to connect to the default URL bolt://neo4j:neo4j@localhost:7687

    If a file is specified, the tool will write the class definitions to that file.
    If no file is specified, the tool will print the class definitions to stdout.

    Note : this script only has a synchronous mode.
    
    options:
        -h, --help            show this help message and exit
        -T, --file-type <arrows|puml>
                            File type to produce. Accepts PlantUML (puml) or Arrows.app (arrows). Default is Arrows.
        -D, --write-to-dir someapp/diagrams
                            Directory where to write output file. Default is current directory.
"""

import argparse
import json
import math
import os
import textwrap

from neomodel import (
    ArrayProperty,
    AsyncRelationshipFrom,
    AsyncRelationshipTo,
    AsyncStructuredNode,
    BooleanProperty,
    DateProperty,
    DateTimeFormatProperty,
    DateTimeNeo4jFormatProperty,
    DateTimeProperty,
    FloatProperty,
    IntegerProperty,
    RelationshipFrom,
    RelationshipTo,
    StringProperty,
    StructuredNode,
    UniqueIdProperty,
)
from neomodel.contrib import AsyncSemiStructuredNode, SemiStructuredNode
from neomodel.contrib.spatial_properties import PointProperty
from neomodel.scripts.utils import load_python_module_or_file, recursive_list_classes


def generate_plantuml(classes):
    filename = "model_diagram.puml"
    diagram = "@startuml\n"

    dot_output = "digraph G {\n"
    dot_output += "  node [shape=record];\n"
    for cls in classes:
        # Node label construction for properties
        label = f"{cls.__name__}|{{"
        properties = [
            f"{prop}: {parse_property_key(cls.defined_properties(aliases=False, rels=False)[prop])}"
            for prop in cls.defined_properties(aliases=False, rels=False)
        ]
        label += " \l ".join(properties)
        label += "}}"

        # Node definition
        dot_output += f'  {cls.__name__} [label="{label}"];\n'

        # Relationships
        for rel_name, rel in cls.defined_properties(
            aliases=False, properties=False
        ).items():
            target_cls = rel._raw_class
            edge_label = f"{rel_name}: {rel.__class__.__name__}"
            if isinstance(rel, RelationshipTo) or isinstance(rel, AsyncRelationshipTo):
                dot_output += (
                    f'  {cls.__name__} -> {target_cls} [label="{edge_label}"];\n'
                )
            elif isinstance(rel, RelationshipFrom) or isinstance(
                rel, AsyncRelationshipFrom
            ):
                dot_output += (
                    f'  {target_cls} -> {cls.__name__} [label="{edge_label}"];\n'
                )

    dot_output += "}"
    diagram += dot_output
    diagram += "@enduml"
    return filename, diagram


def transform_property_type(prop_definition):
    if isinstance(prop_definition, StringProperty):
        return "str"
    elif isinstance(prop_definition, UniqueIdProperty):
        return "id"
    elif isinstance(prop_definition, BooleanProperty):
        return "bool"
    elif isinstance(prop_definition, DateProperty):
        return "date"
    elif (
        isinstance(prop_definition, DateTimeProperty)
        or isinstance(prop_definition, DateTimeFormatProperty)
        or isinstance(prop_definition, DateTimeNeo4jFormatProperty)
    ):
        return "datetime"
    elif isinstance(prop_definition, IntegerProperty):
        return "int"
    elif isinstance(prop_definition, FloatProperty):
        return "float"
    elif isinstance(prop_definition, ArrayProperty):
        return f"list[{transform_property_type(prop_definition.base_property)}]"
    elif isinstance(prop_definition, PointProperty):
        return "point"


def parse_property_key(prop_definition):
    output = transform_property_type(prop_definition)

    if (
        prop_definition.required
        or prop_definition.index
        or prop_definition.unique_index
    ):
        output += " - "
        suffixes = []
        if prop_definition.required:
            suffixes.append("required")
        elif prop_definition.unique_index:
            suffixes.append("unique")
        if prop_definition.index:
            suffixes.append("index")
        output += ", ".join(suffixes)
    return output


def generate_arrows_json(classes):
    filename = "model_diagram.json"
    nodes = []
    edges = []
    positions = {"x": 0, "y": 0}
    radius_increment = 400  # Horizontal space between nodes

    for idx, cls in enumerate(classes):
        node_id = f"n{idx}"
        # Set positions such that related nodes are close on the y-axis
        position = {"x": positions["x"], "y": positions["y"]}
        if idx != 0 and idx % 6 == 0:
            radius_increment += radius_increment
            positions["x"] += radius_increment
            positions["y"] = 0
        else:
            angle = (idx % 6) * (2 * math.pi / 6) + (math.pi / 6)
            if idx % 12 > 6:
                angle += math.pi / 6
            positions["x"] = radius_increment * math.cos(angle)
            positions["y"] = radius_increment * math.sin(angle)

        nodes.append(
            {
                "id": node_id,
                "position": position,
                "caption": "",
                "style": {},
                "labels": [cls.__name__],
                "properties": {
                    prop: parse_property_key(
                        cls.defined_properties(aliases=False, rels=False)[prop]
                    )
                    for prop in cls.defined_properties(aliases=False, rels=False)
                },
            }
        )

        # Prepare relationships
        for _, rel in cls.defined_properties(aliases=False, properties=False).items():
            target_cls = [
                _class for _class in classes if _class.__name__ == rel._raw_class
            ][0]
            target_idx = classes.index(target_cls)
            target_id = f"n{target_idx}"
            # Create edges
            edges.append(
                {
                    "id": f"e{len(edges)}",
                    "type": rel.definition["relation_type"],
                    "style": {},
                    "properties": {},
                    "fromId": node_id
                    if (
                        isinstance(rel, RelationshipTo)
                        or isinstance(rel, AsyncRelationshipTo)
                    )
                    else target_id,
                    "toId": target_id
                    if (
                        isinstance(rel, RelationshipTo)
                        or isinstance(rel, AsyncRelationshipTo)
                    )
                    else node_id,
                }
            )

    return filename, json.dumps(
        {
            "style": {
                "node-color": "#ffffff",
                "border-color": "#000000",
                "caption-color": "#000000",
                "arrow-color": "#000000",
                "label-background-color": "#ffffff",
                "directionality": "directed",
                "arrow-width": 5,
            },
            "nodes": nodes,
            "relationships": edges,
        },
        indent=4,
    )


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description=textwrap.dedent(
            """
            Connects to a Neo4j database and inspects existing nodes and relationships.
            Infers the schema of the database and generates Python class definitions.

            If a connection URL is not specified, the tool will look up the environment 
            variable NEO4J_BOLT_URL. If that environment variable is not set, the tool
            will attempt to connect to the default URL bolt://neo4j:neo4j@localhost:7687

            If a file is specified, the tool will write the class definitions to that file.
            If no file is specified, the tool will print the class definitions to stdout.
            """
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "apps",
        metavar="<someapp/models/app.py>",
        type=str,
        nargs="+",
        help="python modules or files with neomodel schema declarations.",
    )

    parser.add_argument(
        "-T",
        "--file-type",
        metavar="<arrows|puml>",
        type=str,
        default="arrows",
        help="File type to produce. Accepts : [arrows, puml]. Default is arrows.",
    )

    parser.add_argument(
        "-D",
        "--write-to-dir",
        metavar="someapp/diagrams",
        type=str,
        default=".",
        help="Directory where to write output file. Default is current directory.",
    )

    args = parser.parse_args()

    for app in args.apps:
        load_python_module_or_file(app)

    classes = recursive_list_classes(StructuredNode, exclude_list=[SemiStructuredNode])
    classes += recursive_list_classes(
        AsyncStructuredNode, exclude_list=[AsyncSemiStructuredNode]
    )

    filename = ""
    output = ""
    if args.file_type == "puml":
        filename, output = generate_plantuml(classes)
    elif args.file_type == "arrows":
        filename, output = generate_arrows_json(classes)
    else:
        raise ValueError(f"Unsupported file type : {args.file_type}")

    # Save to a file
    with open(os.path.join(args.write_to_dir, filename), "w", encoding="utf-8") as file:
        file.write(output)
        print("Successfully wrote diagram to file : ", file.name)


if __name__ == "__main__":
    main()
