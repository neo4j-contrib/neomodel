from test.utils import get_db_constraints_as_dict, get_db_indexes_as_dict

from six import StringIO

from neomodel import (
    RelationshipTo,
    StringProperty,
    StructuredNode,
    StructuredRel,
    UniqueIdProperty,
    config,
    install_all_labels,
    install_labels,
)
from neomodel.core import db, drop_constraints

config.AUTO_INSTALL_LABELS = False


class NodeWithIndex(StructuredNode):
    name = StringProperty(index=True)


class NodeWithConstraint(StructuredNode):
    name = StringProperty(unique_index=True)


class NodeWithRelationship(StructuredNode):
    ...


class IndexedRelationship(StructuredRel):
    indexed_rel_prop = StringProperty(index=True)


class OtherNodeWithRelationship(StructuredNode):
    has_rel = RelationshipTo(
        NodeWithRelationship, "INDEXED_REL", model=IndexedRelationship
    )


class AbstractNode(StructuredNode):
    __abstract_node__ = True
    name = StringProperty(unique_index=True)


class SomeNotUniqueNode(StructuredNode):
    id_ = UniqueIdProperty(db_property="id")


config.AUTO_INSTALL_LABELS = True


def test_labels_were_not_installed():
    bob = NodeWithConstraint(name="bob").save()
    bob2 = NodeWithConstraint(name="bob").save()
    bob3 = NodeWithConstraint(name="bob").save()
    assert bob.id != bob3.id

    for n in NodeWithConstraint.nodes.all():
        n.delete()


def test_install_all():
    drop_constraints()
    install_labels(AbstractNode)
    # run install all labels
    install_all_labels()

    indexes = get_db_indexes_as_dict()
    index_names = [index["name"] for index in indexes]
    assert "index_INDEXED_REL_indexed_rel_prop" in index_names

    constraints = get_db_constraints_as_dict()
    constraint_names = [constraint["name"] for constraint in constraints]
    assert "constraint_unique_NodeWithConstraint_name" in constraint_names
    assert "constraint_unique_SomeNotUniqueNode_id" in constraint_names

    # remove constraint for above test
    _drop_constraints_for_label_and_property("NoConstraintsSetup", "name")


def test_install_label_twice(capsys):
    expected_std_out = (
        "{code: Neo.ClientError.Schema.EquivalentSchemaRuleAlreadyExists}"
    )
    install_labels(AbstractNode)
    install_labels(AbstractNode)

    install_labels(NodeWithIndex)
    install_labels(NodeWithIndex, quiet=False)
    captured = capsys.readouterr()
    assert expected_std_out in captured.out

    install_labels(NodeWithConstraint)
    install_labels(NodeWithConstraint, quiet=False)
    captured = capsys.readouterr()
    assert expected_std_out in captured.out

    install_labels(OtherNodeWithRelationship)
    install_labels(OtherNodeWithRelationship, quiet=False)
    captured = capsys.readouterr()
    assert expected_std_out in captured.out


def test_install_labels_db_property():
    stdout = StringIO()
    drop_constraints()
    install_labels(SomeNotUniqueNode, quiet=False, stdout=stdout)
    assert "id" in stdout.getvalue()
    # make sure that the id_ constraint doesn't exist
    constraint_names = _drop_constraints_for_label_and_property(
        "SomeNotUniqueNode", "id_"
    )
    assert constraint_names == []
    # make sure the id constraint exists and can be removed
    _drop_constraints_for_label_and_property("SomeNotUniqueNode", "id")


def _drop_constraints_for_label_and_property(label: str = None, property: str = None):
    results, meta = db.cypher_query("SHOW CONSTRAINTS")
    results_as_dict = [dict(zip(meta, row)) for row in results]
    constraint_names = [
        constraint
        for constraint in results_as_dict
        if constraint["labelsOrTypes"] == label and constraint["properties"] == property
    ]
    for constraint_name in constraint_names:
        db.cypher_query(f"DROP CONSTRAINT {constraint_name}")

    return constraint_names
