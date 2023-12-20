import pytest

from neomodel import (
    AsyncRelationshipTo,
    AsyncStructuredNode,
    AsyncStructuredRel,
    StringProperty,
    UniqueIdProperty,
    config,
)
from neomodel._async.core import adb
from neomodel.exceptions import ConstraintValidationFailed, FeatureNotSupported

config.AUTO_INSTALL_LABELS = False


class NodeWithIndex(AsyncStructuredNode):
    name = StringProperty(index=True)


class NodeWithConstraint(AsyncStructuredNode):
    name = StringProperty(unique_index=True)


class NodeWithRelationship(AsyncStructuredNode):
    ...


class IndexedRelationship(AsyncStructuredRel):
    indexed_rel_prop = StringProperty(index=True)


class OtherNodeWithRelationship(AsyncStructuredNode):
    has_rel = AsyncRelationshipTo(
        NodeWithRelationship, "INDEXED_REL", model=IndexedRelationship
    )


class AbstractNode(AsyncStructuredNode):
    __abstract_node__ = True
    name = StringProperty(unique_index=True)


class SomeNotUniqueNode(AsyncStructuredNode):
    id_ = UniqueIdProperty(db_property="id")


config.AUTO_INSTALL_LABELS = True


def test_labels_were_not_installed():
    bob = NodeWithConstraint(name="bob").save()
    bob2 = NodeWithConstraint(name="bob").save()
    bob3 = NodeWithConstraint(name="bob").save()
    assert bob.element_id != bob3.element_id

    for n in NodeWithConstraint.nodes.all():
        n.delete()


def test_install_all():
    adb.drop_constraints()
    adb.install_labels(AbstractNode)
    # run install all labels
    adb.install_all_labels()

    indexes = adb.list_indexes()
    index_names = [index["name"] for index in indexes]
    assert "index_INDEXED_REL_indexed_rel_prop" in index_names

    constraints = adb.list_constraints()
    constraint_names = [constraint["name"] for constraint in constraints]
    assert "constraint_unique_NodeWithConstraint_name" in constraint_names
    assert "constraint_unique_SomeNotUniqueNode_id" in constraint_names

    # remove constraint for above test
    _drop_constraints_for_label_and_property("NoConstraintsSetup", "name")


def test_install_label_twice(capsys):
    expected_std_out = (
        "{code: Neo.ClientError.Schema.EquivalentSchemaRuleAlreadyExists}"
    )
    adb.install_labels(AbstractNode)
    adb.install_labels(AbstractNode)

    adb.install_labels(NodeWithIndex)
    adb.install_labels(NodeWithIndex, quiet=False)
    captured = capsys.readouterr()
    assert expected_std_out in captured.out

    adb.install_labels(NodeWithConstraint)
    adb.install_labels(NodeWithConstraint, quiet=False)
    captured = capsys.readouterr()
    assert expected_std_out in captured.out

    adb.install_labels(OtherNodeWithRelationship)
    adb.install_labels(OtherNodeWithRelationship, quiet=False)
    captured = capsys.readouterr()
    assert expected_std_out in captured.out

    if adb.version_is_higher_than("5.7"):

        class UniqueIndexRelationship(AsyncStructuredRel):
            unique_index_rel_prop = StringProperty(unique_index=True)

        class OtherNodeWithUniqueIndexRelationship(AsyncStructuredNode):
            has_rel = AsyncRelationshipTo(
                NodeWithRelationship, "UNIQUE_INDEX_REL", model=UniqueIndexRelationship
            )

        adb.install_labels(OtherNodeWithUniqueIndexRelationship)
        adb.install_labels(OtherNodeWithUniqueIndexRelationship, quiet=False)
        captured = capsys.readouterr()
        assert expected_std_out in captured.out


def test_install_labels_db_property(capsys):
    adb.drop_constraints()
    adb.install_labels(SomeNotUniqueNode, quiet=False)
    captured = capsys.readouterr()
    assert "id" in captured.out
    # make sure that the id_ constraint doesn't exist
    constraint_names = _drop_constraints_for_label_and_property(
        "SomeNotUniqueNode", "id_"
    )
    assert constraint_names == []
    # make sure the id constraint exists and can be removed
    _drop_constraints_for_label_and_property("SomeNotUniqueNode", "id")


@pytest.mark.skipif(
    adb.version_is_higher_than("5.7"), reason="Not supported before 5.7"
)
def test_relationship_unique_index_not_supported():
    class UniqueIndexRelationship(AsyncStructuredRel):
        name = StringProperty(unique_index=True)

    class TargetNodeForUniqueIndexRelationship(AsyncStructuredNode):
        pass

    with pytest.raises(
        FeatureNotSupported, match=r".*Please upgrade to Neo4j 5.7 or higher"
    ):

        class NodeWithUniqueIndexRelationship(AsyncStructuredNode):
            has_rel = AsyncRelationshipTo(
                TargetNodeForUniqueIndexRelationship,
                "UNIQUE_INDEX_REL",
                model=UniqueIndexRelationship,
            )


@pytest.mark.skipif(not adb.version_is_higher_than("5.7"), reason="Supported from 5.7")
def test_relationship_unique_index():
    class UniqueIndexRelationshipBis(AsyncStructuredRel):
        name = StringProperty(unique_index=True)

    class TargetNodeForUniqueIndexRelationship(AsyncStructuredNode):
        pass

    class NodeWithUniqueIndexRelationship(AsyncStructuredNode):
        has_rel = AsyncRelationshipTo(
            TargetNodeForUniqueIndexRelationship,
            "UNIQUE_INDEX_REL_BIS",
            model=UniqueIndexRelationshipBis,
        )

    adb.install_labels(UniqueIndexRelationshipBis)
    node1 = NodeWithUniqueIndexRelationship().save()
    node2 = TargetNodeForUniqueIndexRelationship().save()
    node3 = TargetNodeForUniqueIndexRelationship().save()
    rel1 = node1.has_rel.connect(node2, {"name": "rel1"})

    with pytest.raises(
        ConstraintValidationFailed,
        match=r".*already exists with type `UNIQUE_INDEX_REL_BIS` and property `name`.*",
    ):
        rel2 = node1.has_rel.connect(node3, {"name": "rel1"})


def _drop_constraints_for_label_and_property(label: str = None, property: str = None):
    results, meta = adb.cypher_query("SHOW CONSTRAINTS")
    results_as_dict = [dict(zip(meta, row)) for row in results]
    constraint_names = [
        constraint
        for constraint in results_as_dict
        if constraint["labelsOrTypes"] == label and constraint["properties"] == property
    ]
    for constraint_name in constraint_names:
        adb.cypher_query(f"DROP CONSTRAINT {constraint_name}")

    return constraint_names
