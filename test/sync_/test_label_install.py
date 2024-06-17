import io
from test._async_compat import mark_sync_test
from unittest.mock import patch

import pytest

from neomodel import (
    RelationshipTo,
    StringProperty,
    StructuredNode,
    StructuredRel,
    UniqueIdProperty,
    db,
)
from neomodel.exceptions import ConstraintValidationFailed, FeatureNotSupported


class NodeWithIndex(StructuredNode):
    name = StringProperty(index=True)


class NodeWithConstraint(StructuredNode):
    name = StringProperty(unique_index=True)


class NodeWithRelationship(StructuredNode): ...


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


@mark_sync_test
def test_install_all():
    db.drop_constraints()
    db.drop_indexes()
    db.install_labels(AbstractNode)
    # run install all labels
    db.install_all_labels()

    indexes = db.list_indexes()
    index_names = [index["name"] for index in indexes]
    assert "index_INDEXED_REL_indexed_rel_prop" in index_names

    constraints = db.list_constraints()
    constraint_names = [constraint["name"] for constraint in constraints]
    assert "constraint_unique_NodeWithConstraint_name" in constraint_names
    assert "constraint_unique_SomeNotUniqueNode_id" in constraint_names

    # remove constraint for above test
    _drop_constraints_for_label_and_property("NoConstraintsSetup", "name")


@mark_sync_test
def test_install_label_twice(capsys):
    db.drop_constraints()
    db.drop_indexes()
    expected_std_out = (
        "{code: Neo.ClientError.Schema.EquivalentSchemaRuleAlreadyExists}"
    )
    db.install_labels(AbstractNode)
    db.install_labels(AbstractNode)

    db.install_labels(NodeWithIndex)
    db.install_labels(NodeWithIndex, quiet=False)
    captured = capsys.readouterr()
    assert expected_std_out in captured.out

    db.install_labels(NodeWithConstraint)
    db.install_labels(NodeWithConstraint, quiet=False)
    captured = capsys.readouterr()
    assert expected_std_out in captured.out

    db.install_labels(OtherNodeWithRelationship)
    db.install_labels(OtherNodeWithRelationship, quiet=False)
    captured = capsys.readouterr()
    assert expected_std_out in captured.out

    if db.version_is_higher_than("5.7"):

        class UniqueIndexRelationship(StructuredRel):
            unique_index_rel_prop = StringProperty(unique_index=True)

        class OtherNodeWithUniqueIndexRelationship(StructuredNode):
            has_rel = RelationshipTo(
                NodeWithRelationship, "UNIQUE_INDEX_REL", model=UniqueIndexRelationship
            )

        db.install_labels(OtherNodeWithUniqueIndexRelationship)
        db.install_labels(OtherNodeWithUniqueIndexRelationship, quiet=False)
        captured = capsys.readouterr()
        assert expected_std_out in captured.out


@mark_sync_test
def test_install_labels_db_property(capsys):
    db.drop_constraints()
    db.install_labels(SomeNotUniqueNode, quiet=False)
    captured = capsys.readouterr()
    assert "id" in captured.out
    # make sure that the id_ constraint doesn't exist
    constraint_names = _drop_constraints_for_label_and_property(
        "SomeNotUniqueNode", "id_"
    )
    assert constraint_names == []
    # make sure the id constraint exists and can be removed
    _drop_constraints_for_label_and_property("SomeNotUniqueNode", "id")


@mark_sync_test
def test_relationship_unique_index_not_supported():
    if db.version_is_higher_than("5.7"):
        pytest.skip("Not supported before 5.7")

    class UniqueIndexRelationship(StructuredRel):
        name = StringProperty(unique_index=True)

    class TargetNodeForUniqueIndexRelationship(StructuredNode):
        pass

    with pytest.raises(
        FeatureNotSupported, match=r".*Please upgrade to Neo4j 5.7 or higher"
    ):

        class NodeWithUniqueIndexRelationship(StructuredNode):
            has_rel = RelationshipTo(
                TargetNodeForUniqueIndexRelationship,
                "UNIQUE_INDEX_REL",
                model=UniqueIndexRelationship,
            )

        db.install_labels(NodeWithUniqueIndexRelationship)


@mark_sync_test
def test_relationship_unique_index():
    if not db.version_is_higher_than("5.7"):
        pytest.skip("Not supported before 5.7")

    class UniqueIndexRelationshipBis(StructuredRel):
        name = StringProperty(unique_index=True)

    class TargetNodeForUniqueIndexRelationship(StructuredNode):
        pass

    class NodeWithUniqueIndexRelationship(StructuredNode):
        has_rel = RelationshipTo(
            TargetNodeForUniqueIndexRelationship,
            "UNIQUE_INDEX_REL_BIS",
            model=UniqueIndexRelationshipBis,
        )

    db.install_labels(NodeWithUniqueIndexRelationship)
    node1 = NodeWithUniqueIndexRelationship().save()
    node2 = TargetNodeForUniqueIndexRelationship().save()
    node3 = TargetNodeForUniqueIndexRelationship().save()
    rel1 = node1.has_rel.connect(node2, {"name": "rel1"})

    with pytest.raises(
        ConstraintValidationFailed,
        match=r".*already exists with type `UNIQUE_INDEX_REL_BIS` and property `name`.*",
    ):
        rel2 = node1.has_rel.connect(node3, {"name": "rel1"})


@mark_sync_test
def test_fulltext_index():
    if not db.version_is_higher_than("5.16"):
        pytest.skip("Not supported before 5.16")

    class FullTextIndexNode(StructuredNode):
        name = StringProperty(fulltext_index=True, fulltext_eventually_consistent=True)

    db.install_labels(FullTextIndexNode)
    indexes = db.list_indexes()
    index_names = [index["name"] for index in indexes]
    assert "fulltext_index_FullTextIndexNode_name" in index_names

    db.cypher_query("DROP INDEX fulltext_index_FullTextIndexNode_name")


@mark_sync_test
def test_fulltext_index_conflict():
    if not db.version_is_higher_than("5.16"):
        pytest.skip("Not supported before 5.16")

    stream = io.StringIO()

    with patch("sys.stdout", new=stream):
        db.cypher_query(
            "CREATE FULLTEXT INDEX FOR (n:FullTextIndexNode) ON EACH [n.name]"
        )

        class FullTextIndexNode(StructuredNode):
            name = StringProperty(fulltext_index=True)

        db.install_labels(FullTextIndexNode)

    console_output = stream.getvalue()
    assert "There already exists an index" in console_output


@mark_sync_test
def test_fulltext_index_not_supported():
    if db.version_is_higher_than("5.16"):
        pytest.skip("Test only for versions lower than 5.16")

    with pytest.raises(
        FeatureNotSupported, match=r".*Please upgrade to Neo4j 5.16 or higher"
    ):

        class FullTextIndexNode(StructuredNode):
            name = StringProperty(fulltext_index=True)

        db.install_labels(FullTextIndexNode)


@mark_sync_test
def test_rel_fulltext_index():
    if not db.version_is_higher_than("5.16"):
        pytest.skip("Not supported before 5.16")

    class FullTextIndexRel(StructuredRel):
        name = StringProperty(fulltext_index=True, fulltext_eventually_consistent=True)

    class FullTextIndexRelNode(StructuredNode):
        has_rel = RelationshipTo(
            "FullTextIndexRelNode", "FULLTEXT_INDEX_REL", model=FullTextIndexRel
        )

    db.install_labels(FullTextIndexRelNode)
    indexes = db.list_indexes()
    index_names = [index["name"] for index in indexes]
    assert "fulltext_index_FULLTEXT_INDEX_REL_name" in index_names

    db.cypher_query("DROP INDEX fulltext_index_FULLTEXT_INDEX_REL_name")


@mark_sync_test
def test_rel_fulltext_index_conflict():
    if not db.version_is_higher_than("5.16"):
        pytest.skip("Not supported before 5.16")

    stream = io.StringIO()

    with patch("sys.stdout", new=stream):
        db.cypher_query(
            "CREATE FULLTEXT INDEX FOR ()-[r:FULLTEXT_INDEX_REL]-() ON EACH [r.name]"
        )

        class FullTextIndexRelConflict(StructuredRel):
            name = StringProperty(
                fulltext_index=True, fulltext_eventually_consistent=True
            )

        class FullTextIndexRelConflictNode(StructuredNode):
            has_rel = RelationshipTo(
                "FullTextIndexRelConflictNode",
                "FULLTEXT_INDEX_REL_CONFLICT",
                model=FullTextIndexRelConflict,
            )

        db.install_labels(FullTextIndexRelConflictNode)

    console_output = stream.getvalue()
    assert "There already exists an index" in console_output


@mark_sync_test
def test_rel_fulltext_index_not_supported():
    if db.version_is_higher_than("5.16"):
        pytest.skip("Test only for versions lower than 5.16")

    with pytest.raises(
        FeatureNotSupported, match=r".*Please upgrade to Neo4j 5.16 or higher"
    ):

        class FullTextIndexRelOld(StructuredRel):
            name = StringProperty(
                fulltext_index=True, fulltext_eventually_consistent=True
            )

        class FullTextIndexRelOldNode(StructuredNode):
            has_rel = RelationshipTo(
                "FullTextIndexRelOldNode",
                "FULLTEXT_INDEX_REL_OLD",
                model=FullTextIndexRelOld,
            )

        db.install_labels(FullTextIndexRelOldNode)


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
