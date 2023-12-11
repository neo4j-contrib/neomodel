"""
.. _neomodel_inspect_database:

``_neomodel_inspect_database``
---------------------------

::

    usage: _neomodel_inspect_database [-h] [--db bolt://neo4j:neo4j@localhost:7687] [--write-to <someapp/models.py> ...]
    
    Connects to a Neo4j database and inspects existing nodes and relationships.
    Infers the schema of the database and generates Python class definitions.

    If a connection URL is not specified, the tool will look up the environment 
    variable NEO4J_BOLT_URL. If that environment variable is not set, the tool
    will attempt to connect to the default URL bolt://neo4j:neo4j@localhost:7687

    If a file is specified, the tool will write the class definitions to that file.
    If no file is specified, the tool will print the class definitions to stdout.
    
    options:
        -h, --help            show this help message and exit
        --db bolt://neo4j:neo4j@localhost:7687
                            Neo4j Server URL
        -T, --write-to someapp/models.py
                            File where to write output.
        --no-rel-props        Do not inspect relationship properties
        --no-rel-cardinality  Do not infer relationship cardinality
"""

import argparse
import string
import textwrap
from os import environ

from neomodel import db

IMPORTS = []


def parse_prop_class(prop_type):
    _import = ""
    prop_class = ""
    if prop_type.startswith("LIST OF"):
        _import = "ArrayProperty"
        prop_class = (
            f"ArrayProperty({parse_prop_class(prop_type.replace('LIST OF ', ''))})"
        )
    else:
        if prop_type == "STRING":
            _import = "StringProperty"
            prop_class = f"{_import}("
        elif prop_type == "BOOLEAN":
            _import = "BooleanProperty"
            prop_class = f"{_import}("
        elif prop_type == "DATE_TIME":
            _import = "DateTimeProperty"
            prop_class = f"{_import}("
        elif prop_type == "INTEGER":
            _import = "IntegerProperty"
            prop_class = f"{_import}("
        elif prop_type == "FLOAT":
            _import = "FloatProperty"
            prop_class = f"{_import}("
        elif prop_type == "POINT":
            _import = "PointProperty"
            prop_class = f"{_import}(crs='wgs-84'"

    if _import not in IMPORTS:
        IMPORTS.append(_import)
    return prop_class


class NodeInspector:
    @staticmethod
    def get_properties_for_label(label):
        query = f"""
          MATCH (n:`{label}`)
          WITH DISTINCT keys(n) as properties, head(collect(n)) AS sampleNode
          ORDER BY size(properties) DESC
          RETURN apoc.meta.cypher.types(properties(sampleNode)) AS properties LIMIT 1
        """
        result, _ = db.cypher_query(query)
        if result is not None and len(result) > 0:
            return result[0][0]

    @staticmethod
    def get_constraints_for_label(label):
        constraints, meta_constraints = db.cypher_query(
            f"SHOW CONSTRAINTS WHERE entityType='NODE' AND '{label}' IN labelsOrTypes AND type='UNIQUENESS'"
        )
        constraints_as_dict = [dict(zip(meta_constraints, row)) for row in constraints]
        constrained_properties = [
            item.get("properties")[0]
            for item in constraints_as_dict
            if len(item.get("properties")) == 1
        ]
        return constrained_properties

    @staticmethod
    def get_indexed_properties_for_label(label):
        if db.version_is_higher_than("5.0"):
            indexes, meta_indexes = db.cypher_query(
                f"SHOW INDEXES WHERE entityType='NODE' AND '{label}' IN labelsOrTypes AND type='RANGE' AND owningConstraint IS NULL"
            )
        else:
            indexes, meta_indexes = db.cypher_query(
                f"SHOW INDEXES WHERE entityType='NODE' AND '{label}' IN labelsOrTypes AND type='BTREE' AND uniqueness='NONUNIQUE'"
            )
        indexes_as_dict = [dict(zip(meta_indexes, row)) for row in indexes]
        indexed_properties = [
            item.get("properties")[0]
            for item in indexes_as_dict
            if len(item.get("properties")) == 1
        ]
        return indexed_properties


class RelationshipInspector:
    @classmethod
    def outgoing_relationships(cls, start_label, get_properties: bool = True):
        if get_properties:
            query = f"""
                MATCH (n:`{start_label}`)-[r]->(m)
                WITH DISTINCT type(r) as rel_type, head(labels(m)) AS target_label, keys(r) AS properties, head(collect(r)) AS sampleRel
                ORDER BY size(properties) DESC
                RETURN rel_type, target_label, apoc.meta.cypher.types(properties(sampleRel)) AS properties LIMIT 1
            """
        else:
            query = f"""
                MATCH (n:`{start_label}`)-[r]->(m)
                WITH DISTINCT type(r) as rel_type, head(labels(m)) AS target_label
                RETURN rel_type, target_label, {{}} AS properties LIMIT 1
            """
        result, _ = db.cypher_query(query)
        return [(record[0], record[1], record[2]) for record in result]

    @staticmethod
    def get_constraints_for_type(rel_type):
        constraints, meta_constraints = db.cypher_query(
            f"SHOW CONSTRAINTS WHERE entityType='RELATIONSHIP' AND '{rel_type}' IN labelsOrTypes AND type='RELATIONSHIP_UNIQUENESS'"
        )
        constraints_as_dict = [dict(zip(meta_constraints, row)) for row in constraints]
        constrained_properties = [
            item.get("properties")[0]
            for item in constraints_as_dict
            if len(item.get("properties")) == 1
        ]
        return constrained_properties

    @staticmethod
    def get_indexed_properties_for_type(rel_type):
        if db.version_is_higher_than("5.0"):
            indexes, meta_indexes = db.cypher_query(
                f"SHOW INDEXES WHERE entityType='RELATIONSHIP' AND '{rel_type}' IN labelsOrTypes AND type='RANGE' AND owningConstraint IS NULL"
            )
        else:
            indexes, meta_indexes = db.cypher_query(
                f"SHOW INDEXES WHERE entityType='RELATIONSHIP' AND '{rel_type}' IN labelsOrTypes AND type='BTREE' AND uniqueness='NONUNIQUE'"
            )
        indexes_as_dict = [dict(zip(meta_indexes, row)) for row in indexes]
        indexed_properties = [
            item.get("properties")[0]
            for item in indexes_as_dict
            if len(item.get("properties")) == 1
        ]
        return indexed_properties

    @staticmethod
    def infer_cardinality(rel_type, start_label):
        range_start_query = f"MATCH (n:`{start_label}`) WHERE NOT EXISTS ((n)-[:`{rel_type}`]->()) WITH n LIMIT 1 RETURN count(n)"
        result, _ = db.cypher_query(range_start_query)
        is_start_zero = result[0][0] > 0

        range_end_query = f"""
            MATCH (n:`{start_label}`)-[rel:`{rel_type}`]->()
            WITH n, count(rel) AS rel_count
            WHERE rel_count > 1
            WITH n LIMIT 1
            RETURN count(n)
        """
        result, _ = db.cypher_query(range_end_query)
        is_end_one = result[0][0] == 0

        cardinality = "Zero" if is_start_zero else "One"
        cardinality += "OrOne" if is_end_one and is_start_zero else "OrMore"

        if cardinality not in IMPORTS:
            IMPORTS.append(cardinality)

        return cardinality


def get_node_labels():
    query = "CALL db.labels()"
    result, _ = db.cypher_query(query)
    return [record[0] for record in result]


def build_prop_string(unique_properties, indexed_properties, prop, prop_type):
    is_unique = prop in unique_properties
    is_indexed = prop in indexed_properties
    index_str = ""
    if is_unique:
        index_str = "unique_index=True"
    elif is_indexed:
        index_str = "index=True"
    return f"    {prop.replace(' ', '_')} = {parse_prop_class(prop_type)}{index_str})\n"


def clean_class_member_key(key):
    return key.replace(" ", "_")


def generate_rel_class_name(rel_type):
    # Relationship type best practices are like FRIENDS_WITH
    # We want to convert that to FriendsWithRel
    return string.capwords(rel_type.replace("_", " ")).replace(" ", "") + "Rel"


def parse_imports():
    imports = ""
    if IMPORTS:
        special_imports = ""
        if "PointProperty" in IMPORTS:
            IMPORTS.remove("PointProperty")
            special_imports += (
                "from neomodel.contrib.spatial_properties import PointProperty\n"
            )
        imports = f"from neomodel import {', '.join(IMPORTS)}\n" + special_imports
    return imports


def build_rel_type_definition(
    label, outgoing_relationships, defined_rel_types, infer_cardinality: bool = True
):
    class_definition_append = ""
    rel_type_definitions = ""

    for rel in outgoing_relationships:
        rel_type = rel[0]
        rel_name = rel_type.lower()
        target_label = rel[1]
        rel_props = rel[2]

        unique_properties = (
            RelationshipInspector.get_constraints_for_type(rel_type)
            if db.version_is_higher_than("5.7")
            else []
        )
        indexed_properties = RelationshipInspector.get_indexed_properties_for_type(
            rel_type
        )

        cardinality_string = ""
        if infer_cardinality:
            cardinality = RelationshipInspector.infer_cardinality(rel_type, label)
            cardinality_string += f", cardinality={cardinality}"

        class_definition_append += f'    {clean_class_member_key(rel_name)} = RelationshipTo("{target_label}", "{rel_type}"{cardinality_string}'

        if rel_props and rel_type not in defined_rel_types:
            rel_model_name = generate_rel_class_name(rel_type)
            class_definition_append += f', model="{rel_model_name}"'
            rel_type_definitions = f"\n\nclass {rel_model_name}(StructuredRel):\n"
            rel_type_definitions += "".join(
                [
                    build_prop_string(
                        unique_properties, indexed_properties, prop, prop_type
                    )
                    for prop, prop_type in rel_props.items()
                ]
            )

        class_definition_append += ")\n"

    class_definition_append += rel_type_definitions

    return class_definition_append


def inspect_database(
    bolt_url,
    get_relationship_properties: bool = True,
    infer_relationship_cardinality: bool = True,
):
    # Connect to the database
    print(f"Connecting to {bolt_url}")
    db.set_connection(bolt_url)

    node_labels = get_node_labels()
    defined_rel_types = []
    class_definitions = ""

    if node_labels:
        IMPORTS.append("StructuredNode")

    for label in node_labels:
        class_name = clean_class_member_key(label)
        properties = NodeInspector.get_properties_for_label(label)
        unique_properties = NodeInspector.get_constraints_for_label(label)
        indexed_properties = NodeInspector.get_indexed_properties_for_label(label)

        class_definition = f"class {class_name}(StructuredNode):\n"
        if properties:
            class_definition += "".join(
                [
                    build_prop_string(
                        unique_properties, indexed_properties, prop, prop_type
                    )
                    for prop, prop_type in properties.items()
                ]
            )

        outgoing_relationships = RelationshipInspector.outgoing_relationships(
            label, get_relationship_properties
        )

        if outgoing_relationships and "StructuredRel" not in IMPORTS:
            IMPORTS.append("RelationshipTo")
            # No rel properties = no rel classes
            # Then StructuredRel import is not needed
            if get_relationship_properties:
                IMPORTS.append("StructuredRel")

        class_definition += build_rel_type_definition(
            label,
            outgoing_relationships,
            defined_rel_types,
            infer_relationship_cardinality,
        )

        if not properties and not outgoing_relationships:
            class_definition += "    pass\n"

        class_definition += "\n\n"

        class_definitions += class_definition

    # Finally, parse imports
    imports = parse_imports()
    output = "\n".join([imports, class_definitions])

    return output


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
        "--db",
        metavar="bolt://neo4j:neo4j@localhost:7687",
        dest="neo4j_bolt_url",
        type=str,
        default="",
        help="Neo4j Server URL",
    )

    parser.add_argument(
        "-T",
        "--write-to",
        metavar="<someapp/models.py>",
        type=str,
        help="File where to write output.",
    )

    parser.add_argument(
        "--no-rel-props",
        dest="get_relationship_properties",
        action="store_false",
        help="Do not inspect relationship properties",
    )

    parser.add_argument(
        "--no-rel-cardinality",
        dest="infer_relationship_cardinality",
        action="store_false",
        help="Do not infer relationship cardinality",
    )

    args = parser.parse_args()

    bolt_url = args.neo4j_bolt_url
    if len(bolt_url) == 0:
        bolt_url = environ.get("NEO4J_BOLT_URL", "bolt://neo4j:neo4j@localhost:7687")

    # If a file is specified, write to that file
    # First try to open the file for writing to make sure it is writable
    # Before connecting to the database
    if args.write_to:
        with open(args.write_to, "w") as file:
            output = inspect_database(
                bolt_url=bolt_url,
                get_relationship_properties=args.get_relationship_properties,
                infer_relationship_cardinality=args.infer_relationship_cardinality,
            )
            print(f"Writing to {args.write_to}")
            file.write(output)
    # If no file is specified, print to stdout
    else:
        print(
            inspect_database(
                bolt_url=bolt_url,
                get_relationship_properties=args.get_relationship_properties,
                infer_relationship_cardinality=args.infer_relationship_cardinality,
            )
        )


if __name__ == "__main__":
    main()
