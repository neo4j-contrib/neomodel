import json
import subprocess

import pytest

from neomodel import (
    RelationshipTo,
    StringProperty,
    StructuredNode,
    StructuredRel,
    config,
)
from neomodel.sync_.core import db


class ScriptsTestRel(StructuredRel):
    some_unique_property = StringProperty(unique_index=db.version_is_higher_than("5.7"))
    some_index_property = StringProperty(index=True)


class ScriptsTestNode(StructuredNode):
    personal_id = StringProperty(unique_index=True)
    name = StringProperty(index=True)
    rel = RelationshipTo("ScriptsTestNode", "REL", model=ScriptsTestRel)
    other_rel = RelationshipTo("ScriptsTestNode", "OTHER_REL")


def test_neomodel_install_labels():
    result = subprocess.run(
        ["neomodel_install_labels", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert "usage: neomodel_install_labels" in result.stdout
    assert result.returncode == 0

    result = subprocess.run(
        ["neomodel_install_labels", "test/test_scripts.py", "--db", db.url],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "Setting up indexes and constraints" in result.stdout
    constraints = db.list_constraints()
    parsed_constraints = [
        (element["type"], element["labelsOrTypes"], element["properties"])
        for element in constraints
    ]
    assert ("UNIQUENESS", ["ScriptsTestNode"], ["personal_id"]) in parsed_constraints
    if db.version_is_higher_than("5.7"):
        assert (
            "RELATIONSHIP_UNIQUENESS",
            ["REL"],
            ["some_unique_property"],
        ) in parsed_constraints
    indexes = db.list_indexes()
    parsed_indexes = [
        (element["labelsOrTypes"], element["properties"]) for element in indexes
    ]
    assert (["ScriptsTestNode"], ["name"]) in parsed_indexes
    assert (["REL"], ["some_index_property"]) in parsed_indexes


def test_neomodel_remove_labels():
    result = subprocess.run(
        ["neomodel_remove_labels", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert "usage: neomodel_remove_labels" in result.stdout
    assert result.returncode == 0

    result = subprocess.run(
        ["neomodel_remove_labels", "--db", config.DATABASE_URL],
        capture_output=True,
        text=True,
        check=False,
    )
    assert (
        "Dropping unique constraint and index on label ScriptsTestNode" in result.stdout
    )
    assert result.returncode == 0
    constraints = db.list_constraints()
    indexes = db.list_indexes(exclude_token_lookup=True)
    assert len(constraints) == 0
    assert len(indexes) == 0


@pytest.mark.parametrize(
    "script_flavour",
    [
        "",
        "_light",
    ],
)
def test_neomodel_inspect_database(script_flavour):
    output_file = "test/data/neomodel_inspect_database_test_output.py"
    # Check that the help option works
    result = subprocess.run(
        ["neomodel_inspect_database", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert "usage: neomodel_inspect_database" in result.stdout
    assert result.returncode == 0

    db.clear_neo4j_database()
    db.install_labels(ScriptsTestNode)
    db.install_labels(ScriptsTestRel)

    # Create a few nodes and a rel, with indexes and constraints
    node1 = ScriptsTestNode(personal_id="1", name="test").save()
    node2 = ScriptsTestNode(personal_id="2", name="test").save()
    node3 = ScriptsTestNode(personal_id="3", name="test").save()
    node1.rel.connect(node2, {"some_unique_property": "1", "some_index_property": "2"})
    node1.other_rel.connect(node3)

    # Create a node with all the parsable property types
    # Also create a node with no properties
    db.cypher_query(
        """
        CREATE (:EveryPropertyTypeNode {
            string_property: "Hello World",
            boolean_property: true,
            date_property: date("2020-01-01"),
            datetime_property: datetime("2020-01-01T00:00:00.000Z"),
            integer_property: 1,
            float_property: 1.0,
            point_property: point({x: 0.0, y: 0.0, crs: "wgs-84"}),
            array_property: ["test"]
        })
        CREATE (:NoPropertyNode)
        CREATE (n1:NoPropertyRelNode)
        CREATE (n2:NoPropertyRelNode)
        CREATE (n1)-[:NO_PROP_REL]->(n2)
        """
    )

    # Test the console output version of the script
    args_list = ["neomodel_inspect_database", "--db", config.DATABASE_URL]
    if script_flavour == "_light":
        args_list += ["--no-rel-props", "--no-rel-cardinality"]
    result = subprocess.run(
        args_list,
        capture_output=True,
        text=True,
        check=True,
    )

    wrapped_console_output = [
        line for line in result.stdout.splitlines() if line.strip()
    ]
    assert wrapped_console_output[0].startswith("Connecting to")
    # Check that all the expected lines are here
    file_path = (
        f"test/data/neomodel_inspect_database_output{script_flavour}.txt"
        if db.version_is_higher_than("5.7")
        else f"test/data/neomodel_inspect_database_output_pre_5_7{script_flavour}.txt"
    )
    with open(file_path, "r") as f:
        wrapped_test_file = [line for line in f.read().split("\n") if line.strip()]
        for line in wrapped_test_file:
            # The neomodel components import order might differ
            # So let's check that every import that should be added is added, regardless of order
            if line.startswith("from neomodel import"):
                parsed_imports = line.replace("from neomodel import ", "").split(", ")
                expected_imports = (
                    wrapped_console_output[1]
                    .replace("from neomodel import ", "")
                    .split(", ")
                )
                assert set(parsed_imports) == set(expected_imports)
                wrapped_test_file.remove(line)
                break

        # Check that both outputs have the same set of lines, regardless of order and redundance
        assert set(wrapped_test_file) == set(wrapped_console_output[2:])

    # Test the file output version of the script
    args_list += ["--write-to", output_file]
    result = subprocess.run(
        args_list,
        capture_output=True,
        text=True,
        check=True,
    )

    # Check that the file was written
    # And that the file output has the same content as the console output
    # Again, regardless of order and redundance
    wrapped_file_console_output = [
        line for line in result.stdout.splitlines() if line.strip()
    ]
    assert wrapped_file_console_output[0].startswith("Connecting to")
    assert wrapped_file_console_output[1].startswith("Writing to")
    with open(output_file, "r") as f:
        wrapped_output_file = [line for line in f.read().split("\n") if line.strip()]
        assert set(wrapped_output_file) == set(wrapped_console_output[1:])

    # Finally, delete the file created by the script
    subprocess.run(
        ["rm", output_file],
    )


def test_neomodel_generate_diagram():
    result = subprocess.run(
        ["neomodel_generate_diagram", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert "usage: neomodel_generate_diagram" in result.stdout
    assert result.returncode == 0

    output_dir = "test/data"

    # Arrows
    result = subprocess.run(
        [
            "neomodel_generate_diagram",
            "test/diagram_classes.py",
            "--file-type",
            "arrows",
            "--write-to-dir",
            output_dir,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert "Loaded test/diagram_classes.py" in result.stdout
    assert "Successfully wrote diagram to file" in result.stdout
    assert result.returncode == 0

    # Check that the output file is as expected
    with open("test/data/model_diagram.json", "r", encoding="utf-8") as f:
        actual_json = json.loads(f.read())
    with open("test/data/expected_model_diagram.json", "r", encoding="utf-8") as f:
        expected_json = json.loads(f.read())
    assert actual_json["style"] == expected_json["style"]
    assert len(actual_json["nodes"]) == len(expected_json["nodes"])
    assert len(actual_json["relationships"]) == len(expected_json["relationships"])

    for index, node in enumerate(actual_json["nodes"]):
        expected_node = expected_json["nodes"][index]
        assert node["id"] == expected_node["id"]
        assert node["labels"] == expected_node["labels"]
        assert node["properties"] == expected_node["properties"]

    assert actual_json["relationships"] == expected_json["relationships"]

    # PlantUML
    puml_result = subprocess.run(
        [
            "neomodel_generate_diagram",
            "test/diagram_classes.py",
            "--file-type",
            "puml",
            "--write-to-dir",
            output_dir,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert "Loaded test/diagram_classes.py" in result.stdout
    assert "Successfully wrote diagram to file" in result.stdout
    assert puml_result.returncode == 0

    # Check that the output file is as expected
    with open("test/data/model_diagram.puml", "r", encoding="utf-8") as f:
        actual_json = f.read()
    with open("test/data/expected_model_diagram.puml", "r", encoding="utf-8") as f:
        expected_json = f.read()
    assert actual_json == expected_json

    # Wrong format
    wrong_result = subprocess.run(
        [
            "neomodel_generate_diagram",
            "test/diagram_classes.py",
            "--file-type",
            "pdf",
            "--write-to-dir",
            output_dir,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert "Unsupported file type : pdf" in wrong_result.stderr
