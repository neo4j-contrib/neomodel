import subprocess

from neomodel import (
    RelationshipTo,
    StringProperty,
    StructuredNode,
    StructuredRel,
    config,
    db,
)


class ScriptsTestRel(StructuredRel):
    some_unique_property = StringProperty(unique_index=True)
    some_index_property = StringProperty(index=True)


class ScriptsTestNode(StructuredNode):
    personal_id = StringProperty(unique_index=True)
    name = StringProperty(index=True)
    rel = RelationshipTo("ScriptsTestNode", "REL", model=ScriptsTestRel)


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
