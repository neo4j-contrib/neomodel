import io
from test._async_compat import mark_async_test
from unittest.mock import patch

import pytest

from neomodel import (
    AsyncRelationshipTo,
    AsyncStructuredNode,
    AsyncStructuredRel,
    StringProperty,
    UniqueIdProperty,
    adb,
)
from neomodel.exceptions import ConstraintValidationFailed, FeatureNotSupported


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


@mark_async_test
async def test_install_all():
    await adb.drop_constraints()
    await adb.drop_indexes()
    await adb.install_labels(AbstractNode)
    # run install all labels
    await adb.install_all_labels()

    indexes = await adb.list_indexes()
    index_names = [index["name"] for index in indexes]
    assert "index_INDEXED_REL_indexed_rel_prop" in index_names

    constraints = await adb.list_constraints()
    constraint_names = [constraint["name"] for constraint in constraints]
    assert "constraint_unique_NodeWithConstraint_name" in constraint_names
    assert "constraint_unique_SomeNotUniqueNode_id" in constraint_names

    # remove constraint for above test
    await _drop_constraints_for_label_and_property("NoConstraintsSetup", "name")


@mark_async_test
async def test_install_label_twice(capsys):
    await adb.drop_constraints()
    await adb.drop_indexes()
    expected_std_out = (
        "{code: Neo.ClientError.Schema.EquivalentSchemaRuleAlreadyExists}"
    )
    await adb.install_labels(AbstractNode)
    await adb.install_labels(AbstractNode)

    await adb.install_labels(NodeWithIndex)
    await adb.install_labels(NodeWithIndex, quiet=False)
    captured = capsys.readouterr()
    assert expected_std_out in captured.out

    await adb.install_labels(NodeWithConstraint)
    await adb.install_labels(NodeWithConstraint, quiet=False)
    captured = capsys.readouterr()
    assert expected_std_out in captured.out

    await adb.install_labels(OtherNodeWithRelationship)
    await adb.install_labels(OtherNodeWithRelationship, quiet=False)
    captured = capsys.readouterr()
    assert expected_std_out in captured.out

    if await adb.version_is_higher_than("5.7"):

        class UniqueIndexRelationship(AsyncStructuredRel):
            unique_index_rel_prop = StringProperty(unique_index=True)

        class OtherNodeWithUniqueIndexRelationship(AsyncStructuredNode):
            has_rel = AsyncRelationshipTo(
                NodeWithRelationship, "UNIQUE_INDEX_REL", model=UniqueIndexRelationship
            )

        await adb.install_labels(OtherNodeWithUniqueIndexRelationship)
        await adb.install_labels(OtherNodeWithUniqueIndexRelationship, quiet=False)
        captured = capsys.readouterr()
        assert expected_std_out in captured.out


@mark_async_test
async def test_install_labels_db_property(capsys):
    await adb.drop_constraints()
    await adb.install_labels(SomeNotUniqueNode, quiet=False)
    captured = capsys.readouterr()
    assert "id" in captured.out
    # make sure that the id_ constraint doesn't exist
    constraint_names = await _drop_constraints_for_label_and_property(
        "SomeNotUniqueNode", "id_"
    )
    assert constraint_names == []
    # make sure the id constraint exists and can be removed
    await _drop_constraints_for_label_and_property("SomeNotUniqueNode", "id")


@mark_async_test
async def test_relationship_unique_index_not_supported():
    if await adb.version_is_higher_than("5.7"):
        pytest.skip("Not supported before 5.7")

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

        await adb.install_labels(NodeWithUniqueIndexRelationship)


@mark_async_test
async def test_relationship_unique_index():
    if not await adb.version_is_higher_than("5.7"):
        pytest.skip("Not supported before 5.7")

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

    await adb.install_labels(NodeWithUniqueIndexRelationship)
    node1 = await NodeWithUniqueIndexRelationship().save()
    node2 = await TargetNodeForUniqueIndexRelationship().save()
    node3 = await TargetNodeForUniqueIndexRelationship().save()
    rel1 = await node1.has_rel.connect(node2, {"name": "rel1"})

    with pytest.raises(
        ConstraintValidationFailed,
        match=r".*already exists with type `UNIQUE_INDEX_REL_BIS` and property `name`.*",
    ):
        rel2 = await node1.has_rel.connect(node3, {"name": "rel1"})


@mark_async_test
async def test_fulltext_index():
    if not await adb.version_is_higher_than("5.16"):
        pytest.skip("Not supported before 5.16")

    class FullTextIndexNode(AsyncStructuredNode):
        name = StringProperty(fulltext_index=True, fulltext_eventually_consistent=True)

    await adb.install_labels(FullTextIndexNode)
    indexes = await adb.list_indexes()
    index_names = [index["name"] for index in indexes]
    assert "fulltext_index_FullTextIndexNode_name" in index_names

    await adb.cypher_query("DROP INDEX fulltext_index_FullTextIndexNode_name")


@mark_async_test
async def test_fulltext_index_conflict():
    if not await adb.version_is_higher_than("5.16"):
        pytest.skip("Not supported before 5.16")

    stream = io.StringIO()

    with patch("sys.stdout", new=stream):
        await adb.cypher_query(
            "CREATE FULLTEXT INDEX FOR (n:FullTextIndexNodeConflict) ON EACH [n.name]"
        )

        class FullTextIndexNodeConflict(AsyncStructuredNode):
            name = StringProperty(fulltext_index=True)

        await adb.install_labels(FullTextIndexNodeConflict)

    console_output = stream.getvalue()
    assert "There already exists an index" in console_output


@mark_async_test
async def test_fulltext_index_not_supported():
    if await adb.version_is_higher_than("5.16"):
        pytest.skip("Test only for versions lower than 5.16")

    with pytest.raises(
        FeatureNotSupported, match=r".*Please upgrade to Neo4j 5.16 or higher"
    ):

        class FullTextIndexNodeOld(AsyncStructuredNode):
            name = StringProperty(fulltext_index=True)

        await adb.install_labels(FullTextIndexNodeOld)


@mark_async_test
async def test_rel_fulltext_index():
    if not await adb.version_is_higher_than("5.16"):
        pytest.skip("Not supported before 5.16")

    class FullTextIndexRel(AsyncStructuredRel):
        name = StringProperty(fulltext_index=True, fulltext_eventually_consistent=True)

    class FullTextIndexRelNode(AsyncStructuredNode):
        has_rel = AsyncRelationshipTo(
            "FullTextIndexRelNode", "FULLTEXT_INDEX_REL", model=FullTextIndexRel
        )

    await adb.install_labels(FullTextIndexRelNode)
    indexes = await adb.list_indexes()
    index_names = [index["name"] for index in indexes]
    assert "fulltext_index_FULLTEXT_INDEX_REL_name" in index_names

    await adb.cypher_query("DROP INDEX fulltext_index_FULLTEXT_INDEX_REL_name")


@mark_async_test
async def test_rel_fulltext_index_conflict():
    if not await adb.version_is_higher_than("5.16"):
        pytest.skip("Not supported before 5.16")

    stream = io.StringIO()

    with patch("sys.stdout", new=stream):
        await adb.cypher_query(
            "CREATE FULLTEXT INDEX FOR ()-[r:FULLTEXT_INDEX_REL_CONFLICT]-() ON EACH [r.name]"
        )

        class FullTextIndexRelConflict(AsyncStructuredRel):
            name = StringProperty(
                fulltext_index=True, fulltext_eventually_consistent=True
            )

        class FullTextIndexRelConflictNode(AsyncStructuredNode):
            has_rel = AsyncRelationshipTo(
                "FullTextIndexRelConflictNode",
                "FULLTEXT_INDEX_REL_CONFLICT",
                model=FullTextIndexRelConflict,
            )

        await adb.install_labels(FullTextIndexRelConflictNode)

    console_output = stream.getvalue()
    assert "There already exists an index" in console_output


@mark_async_test
async def test_rel_fulltext_index_not_supported():
    if await adb.version_is_higher_than("5.16"):
        pytest.skip("Test only for versions lower than 5.16")

    with pytest.raises(
        FeatureNotSupported, match=r".*Please upgrade to Neo4j 5.16 or higher"
    ):

        class FullTextIndexRelOld(AsyncStructuredRel):
            name = StringProperty(
                fulltext_index=True, fulltext_eventually_consistent=True
            )

        class FullTextIndexRelOldNode(AsyncStructuredNode):
            has_rel = AsyncRelationshipTo(
                "FullTextIndexRelOldNode",
                "FULLTEXT_INDEX_REL_OLD",
                model=FullTextIndexRelOld,
            )

        await adb.install_labels(FullTextIndexRelOldNode)


async def _drop_constraints_for_label_and_property(
    label: str = None, property: str = None
):
    results, meta = await adb.cypher_query("SHOW CONSTRAINTS")
    results_as_dict = [dict(zip(meta, row)) for row in results]
    constraint_names = [
        constraint
        for constraint in results_as_dict
        if constraint["labelsOrTypes"] == label and constraint["properties"] == property
    ]
    for constraint_name in constraint_names:
        await adb.cypher_query(f"DROP CONSTRAINT {constraint_name}")

    return constraint_names
