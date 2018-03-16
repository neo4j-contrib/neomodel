from neomodel import StructuredNode, StringProperty, config
from neomodel.db import client, remove_all_labels
from neo4j.exceptions import ClientError

config.AUTO_INSTALL_LABELS = True


class ConstraintAndIndex(StructuredNode):
    name = StringProperty(unique_index=True)
    last_name = StringProperty(index=True)


def test_drop_labels():
    constraints_before, meta = client.cypher_query("CALL db.constraints()")
    indexes_before, meta = client.cypher_query("CALL db.indexes()")

    assert len(constraints_before) > 0
    assert len(indexes_before) > 0

    remove_all_labels()

    constraints, meta = client.cypher_query("CALL db.constraints()")
    indexes, meta = client.cypher_query("CALL db.indexes()")

    assert len(constraints) == 0
    assert len(indexes) == 0

    # Returning all old constraints and indexes
    for constraint in constraints_before:
        client.cypher_query('CREATE ' + constraint[0])
    for index in indexes_before:
        try:
            client.cypher_query('CREATE ' + index[0])
        except ClientError:
            pass
