from six import StringIO
import pytest
from neo4j.exceptions import DatabaseError, CypherSyntaxError
from neomodel import (
    config, StructuredNode, StringProperty, install_all_labels, install_labels,
    UniqueIdProperty)
from neomodel.core import db, drop_constraints


config.AUTO_INSTALL_LABELS = False


class NoConstraintsSetup(StructuredNode):
    name = StringProperty(unique_index=True)


class AbstractNode(StructuredNode):
    __abstract_node__ = True
    name = StringProperty(unique_index=True)


class SomeNotUniqueNode(StructuredNode):
    id_ = UniqueIdProperty(db_property='id')


config.AUTO_INSTALL_LABELS = True


def test_labels_were_not_installed():
    bob = NoConstraintsSetup(name='bob').save()
    bob2 = NoConstraintsSetup(name='bob').save()
    bob3 = NoConstraintsSetup(name='bob').save()
    assert bob.id != bob3.id

    for n in NoConstraintsSetup.nodes.all():
        n.delete()


def test_install_all():
    drop_constraints()
    install_labels(AbstractNode)
    # run install all labels
    install_all_labels()
    # remove constraint for above test
    try:
        _drop_constraints_for_label_and_property("NoConstraintsSetup", "name")
    except CypherSyntaxError:
        db.cypher_query("DROP CONSTRAINT on (n:NoConstraintsSetup) ASSERT n.name IS UNIQUE")


def test_install_label_twice():
    install_labels(AbstractNode)
    install_labels(AbstractNode)


def test_install_labels_db_property():
    stdout = StringIO()
    drop_constraints()
    install_labels(SomeNotUniqueNode, quiet=False, stdout=stdout)
    assert 'id' in stdout.getvalue()
    # make sure that the id_ constraint doesn't exist
    try:
        constraint_names = _drop_constraints_for_label_and_property("SomeNotUniqueNode", "id_")
        assert constraint_names == []
    except CypherSyntaxError:
        with pytest.raises(DatabaseError) as exc_info:
            db.cypher_query(
                'DROP CONSTRAINT on (n:SomeNotUniqueNode) ASSERT n.id_ IS UNIQUE')
        assert 'No such constraint' in exc_info.exconly()
    # make sure the id constraint exists and can be removed
    try:
        _drop_constraints_for_label_and_property("SomeNotUniqueNode", "id")
    except CypherSyntaxError:
        db.cypher_query('DROP CONSTRAINT on (n:SomeNotUniqueNode) ASSERT n.id IS UNIQUE')


def _drop_constraints_for_label_and_property(label: str = None, property: str = None):
    results, meta = db.cypher_query("SHOW CONSTRAINTS")
    results_as_dict = [dict(zip(meta, row)) for row in results]
    constraint_names = [constraint for constraint in results_as_dict if constraint["labelsOrTypes"]==label and constraint["properties"]==property]
    for constraint_name in constraint_names:
        db.cypher_query(f"DROP CONSTRAINT {constraint_name}")

    return constraint_names
