from neomodel import StructuredNode, StringProperty, config
from neomodel.core import db, remove_all_labels
from neo4j.exceptions import ClientError

config.AUTO_INSTALL_LABELS = True


class ConstraintAndIndex(StructuredNode):
    name = StringProperty(unique_index=True)
    last_name = StringProperty(index=True)


def test_drop_labels():
    constraints_before, meta = db.cypher_query("CALL db.constraints()")
    indexes_before, meta = db.cypher_query("CALL db.indexes()")

    assert len(constraints_before) > 0
    assert len(indexes_before) > 0

    remove_all_labels()

    constraints, meta = db.cypher_query("CALL db.constraints()")
    indexes, meta = db.cypher_query("CALL db.indexes()")

    assert len(constraints) == 0
    assert len(indexes) == 0

    # Returning all old constraints and indexes
    # Versions prior to 4.0 have a very different return format
    for constraint in constraints_before:
        if constraint[0].startswith('CONSTRAINT '):
            db.cypher_query('CREATE ' + constraint[0])
        else:
            db.cypher_query('CREATE ' + constraint[1])
    for index in indexes_before:
        try:
            if not isinstance(index[0], int) and index[0].startswith('INDEX '):
                db.cypher_query('CREATE ' + index[0])
            else:
                db.cypher_query('CREATE INDEX {0} FOR (n:{1}) ON (n.{2})'.format(index[1], index[7][0], index[8][0]))
        except ClientError:
            pass
