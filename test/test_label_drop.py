from neo4j.exceptions import ClientError

from neomodel import StringProperty, StructuredNode, config
from neomodel.core import db, remove_all_labels

config.AUTO_INSTALL_LABELS = True


class ConstraintAndIndex(StructuredNode):
    name = StringProperty(unique_index=True)
    last_name = StringProperty(index=True)


def test_drop_labels():
    constraints_before = db.list_constraints()
    indexes_before = db.list_indexes(exclude_token_lookup=True)

    assert len(constraints_before) > 0
    assert len(indexes_before) > 0

    remove_all_labels()

    constraints = db.list_constraints()
    indexes = db.list_indexes(exclude_token_lookup=True)

    assert len(constraints) == 0
    assert len(indexes) == 0

    # Recreating all old constraints and indexes
    for constraint in constraints_before:
        constraint_type_clause = "UNIQUE"
        if constraint["type"] == "NODE_PROPERTY_EXISTENCE":
            constraint_type_clause = "NOT NULL"
        elif constraint["type"] == "NODE_KEY":
            constraint_type_clause = "NODE KEY"

        db.cypher_query(
            f'CREATE CONSTRAINT {constraint["name"]} FOR (n:{constraint["labelsOrTypes"][0]}) REQUIRE n.{constraint["properties"][0]} IS {constraint_type_clause}'
        )
    for index in indexes_before:
        try:
            db.cypher_query(
                f'CREATE INDEX {index["name"]} FOR (n:{index["labelsOrTypes"][0]}) ON (n.{index["properties"][0]})'
            )
        except ClientError:
            pass
