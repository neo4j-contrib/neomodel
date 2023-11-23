from neo4j.exceptions import ClientError

from neomodel import StringProperty, StructuredNodeAsync, config
from neomodel._async.core import adb

config.AUTO_INSTALL_LABELS = True


class ConstraintAndIndex(StructuredNodeAsync):
    name = StringProperty(unique_index=True)
    last_name = StringProperty(index=True)


def test_drop_labels():
    constraints_before = adb.list_constraints_async()
    indexes_before = adb.list_indexes_async(exclude_token_lookup=True)

    assert len(constraints_before) > 0
    assert len(indexes_before) > 0

    adb.remove_all_labels_async()

    constraints = adb.list_constraints_async()
    indexes = adb.list_indexes_async(exclude_token_lookup=True)

    assert len(constraints) == 0
    assert len(indexes) == 0

    # Recreating all old constraints and indexes
    for constraint in constraints_before:
        constraint_type_clause = "UNIQUE"
        if constraint["type"] == "NODE_PROPERTY_EXISTENCE":
            constraint_type_clause = "NOT NULL"
        elif constraint["type"] == "NODE_KEY":
            constraint_type_clause = "NODE KEY"

        adb.cypher_query_async(
            f'CREATE CONSTRAINT {constraint["name"]} FOR (n:{constraint["labelsOrTypes"][0]}) REQUIRE n.{constraint["properties"][0]} IS {constraint_type_clause}'
        )
    for index in indexes_before:
        try:
            adb.cypher_query_async(
                f'CREATE INDEX {index["name"]} FOR (n:{index["labelsOrTypes"][0]}) ON (n.{index["properties"][0]})'
            )
        except ClientError:
            pass
