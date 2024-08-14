import io
from test._async_compat import mark_sync_test
from unittest.mock import patch

import pytest
from neo4j.exceptions import ClientError

from neomodel import (
    ArrayProperty,
    FloatProperty,
    FulltextIndex,
    RelationshipTo,
    StringProperty,
    StructuredNode,
    StructuredRel,
    UniqueIdProperty,
    VectorIndex,
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
        name = StringProperty(fulltext_index=FulltextIndex(eventually_consistent=True))

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
            "CREATE FULLTEXT INDEX FOR (n:FullTextIndexNodeConflict) ON EACH [n.name]"
        )

        class FullTextIndexNodeConflict(StructuredNode):
            name = StringProperty(fulltext_index=FulltextIndex())

        db.install_labels(FullTextIndexNodeConflict, quiet=False)

    console_output = stream.getvalue()
    assert "Creating fulltext index" in console_output
    assert "There already exists an index" in console_output


@mark_sync_test
def test_fulltext_index_not_supported():
    if db.version_is_higher_than("5.16"):
        pytest.skip("Test only for versions lower than 5.16")

    with pytest.raises(
        FeatureNotSupported, match=r".*Please upgrade to Neo4j 5.16 or higher"
    ):

        class FullTextIndexNodeOld(StructuredNode):
            name = StringProperty(fulltext_index=FulltextIndex())

        db.install_labels(FullTextIndexNodeOld)


@mark_sync_test
def test_rel_fulltext_index():
    if not db.version_is_higher_than("5.16"):
        pytest.skip("Not supported before 5.16")

    class FullTextIndexRel(StructuredRel):
        name = StringProperty(fulltext_index=FulltextIndex(eventually_consistent=True))

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
            "CREATE FULLTEXT INDEX FOR ()-[r:FULLTEXT_INDEX_REL_CONFLICT]-() ON EACH [r.name]"
        )

        class FullTextIndexRelConflict(StructuredRel):
            name = StringProperty(
                fulltext_index=FulltextIndex(eventually_consistent=True)
            )

        class FullTextIndexRelConflictNode(StructuredNode):
            has_rel = RelationshipTo(
                "FullTextIndexRelConflictNode",
                "FULLTEXT_INDEX_REL_CONFLICT",
                model=FullTextIndexRelConflict,
            )

        db.install_labels(FullTextIndexRelConflictNode, quiet=False)

    console_output = stream.getvalue()
    assert "Creating fulltext index" in console_output
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
                fulltext_index=FulltextIndex(eventually_consistent=True)
            )

        class FullTextIndexRelOldNode(StructuredNode):
            has_rel = RelationshipTo(
                "FullTextIndexRelOldNode",
                "FULLTEXT_INDEX_REL_OLD",
                model=FullTextIndexRelOld,
            )

        db.install_labels(FullTextIndexRelOldNode)


@mark_sync_test
def test_vector_index():
    if not db.version_is_higher_than("5.15"):
        pytest.skip("Not supported before 5.15")

    class VectorIndexNode(StructuredNode):
        embedding = ArrayProperty(
            FloatProperty(),
            vector_index=VectorIndex(dimensions=256, similarity_function="euclidean"),
        )

    db.install_labels(VectorIndexNode)
    indexes = db.list_indexes()
    index_names = [index["name"] for index in indexes]
    assert "vector_index_VectorIndexNode_embedding" in index_names

    db.cypher_query("DROP INDEX vector_index_VectorIndexNode_embedding")


@mark_sync_test
def test_vector_index_conflict():
    if not db.version_is_higher_than("5.15"):
        pytest.skip("Not supported before 5.15")

    stream = io.StringIO()

    with patch("sys.stdout", new=stream):
        db.cypher_query(
            "CREATE VECTOR INDEX FOR (n:VectorIndexNodeConflict) ON n.embedding OPTIONS{indexConfig:{`vector.similarity_function`:'cosine', `vector.dimensions`:1536}}"
        )

        class VectorIndexNodeConflict(StructuredNode):
            embedding = ArrayProperty(FloatProperty(), vector_index=VectorIndex())

        db.install_labels(VectorIndexNodeConflict, quiet=False)

    console_output = stream.getvalue()
    assert "Creating vector index" in console_output
    assert "There already exists an index" in console_output


@mark_sync_test
def test_vector_index_not_supported():
    if db.version_is_higher_than("5.15"):
        pytest.skip("Test only for versions lower than 5.15")

    with pytest.raises(
        FeatureNotSupported, match=r".*Please upgrade to Neo4j 5.15 or higher"
    ):

        class VectorIndexNodeOld(StructuredNode):
            embedding = ArrayProperty(FloatProperty(), vector_index=VectorIndex())

        db.install_labels(VectorIndexNodeOld)


@mark_sync_test
def test_rel_vector_index():
    if not db.version_is_higher_than("5.18"):
        pytest.skip("Not supported before 5.18")

    class VectorIndexRel(StructuredRel):
        embedding = ArrayProperty(
            FloatProperty(),
            vector_index=VectorIndex(dimensions=256, similarity_function="euclidean"),
        )

    class VectorIndexRelNode(StructuredNode):
        has_rel = RelationshipTo(
            "VectorIndexRelNode", "VECTOR_INDEX_REL", model=VectorIndexRel
        )

    db.install_labels(VectorIndexRelNode)
    indexes = db.list_indexes()
    index_names = [index["name"] for index in indexes]
    assert "vector_index_VECTOR_INDEX_REL_embedding" in index_names

    db.cypher_query("DROP INDEX vector_index_VECTOR_INDEX_REL_embedding")


@mark_sync_test
def test_rel_vector_index_conflict():
    if not db.version_is_higher_than("5.18"):
        pytest.skip("Not supported before 5.18")

    stream = io.StringIO()

    with patch("sys.stdout", new=stream):
        db.cypher_query(
            "CREATE VECTOR INDEX FOR ()-[r:VECTOR_INDEX_REL_CONFLICT]-() ON r.embedding OPTIONS{indexConfig:{`vector.similarity_function`:'cosine', `vector.dimensions`:1536}}"
        )

        class VectorIndexRelConflict(StructuredRel):
            embedding = ArrayProperty(FloatProperty(), vector_index=VectorIndex())

        class VectorIndexRelConflictNode(StructuredNode):
            has_rel = RelationshipTo(
                "VectorIndexRelConflictNode",
                "VECTOR_INDEX_REL_CONFLICT",
                model=VectorIndexRelConflict,
            )

        db.install_labels(VectorIndexRelConflictNode, quiet=False)

    console_output = stream.getvalue()
    assert "Creating vector index" in console_output
    assert "There already exists an index" in console_output


@mark_sync_test
def test_rel_vector_index_not_supported():
    if db.version_is_higher_than("5.18"):
        pytest.skip("Test only for versions lower than 5.18")

    with pytest.raises(
        FeatureNotSupported, match=r".*Please upgrade to Neo4j 5.18 or higher"
    ):

        class VectorIndexRelOld(StructuredRel):
            embedding = ArrayProperty(FloatProperty(), vector_index=VectorIndex())

        class VectorIndexRelOldNode(StructuredNode):
            has_rel = RelationshipTo(
                "VectorIndexRelOldNode",
                "VECTOR_INDEX_REL_OLD",
                model=VectorIndexRelOld,
            )

        db.install_labels(VectorIndexRelOldNode)


@mark_sync_test
def test_unauthorized_index_creation():
    if not db.edition_is_enterprise():
        pytest.skip("Skipping test for community edition")

    unauthorized_user = "troygreene"
    expected_message_index = r".*Schema operation.* not allowed for user.*"

    # Standard node index
    with pytest.raises(
        ClientError,
        match=expected_message_index,
    ):
        with db.impersonate(unauthorized_user):

            class UnauthorizedIndexNode(StructuredNode):
                name = StringProperty(index=True)

            db.install_labels(UnauthorizedIndexNode)

    # Node uniqueness constraint
    with pytest.raises(
        ClientError,
        match=expected_message_index,
    ):
        with db.impersonate(unauthorized_user):

            class UnauthorizedUniqueIndexNode(StructuredNode):
                name = StringProperty(unique_index=True)

            db.install_labels(UnauthorizedUniqueIndexNode)

    # Relationship index
    with pytest.raises(
        ClientError,
        match=expected_message_index,
    ):
        with db.impersonate(unauthorized_user):

            class UnauthorizedRelIndex(StructuredRel):
                name = StringProperty(index=True)

            class UnauthorizedRelIndexNode(StructuredNode):
                has_rel = RelationshipTo(
                    "UnauthorizedRelIndexNode",
                    "UNAUTHORIZED_REL_INDEX",
                    model=UnauthorizedRelIndex,
                )

            db.install_labels(UnauthorizedRelIndexNode)


@mark_sync_test
def test_unauthorized_index_creation_recent_features():
    if not db.edition_is_enterprise() or not db.version_is_higher_than("5.18"):
        pytest.skip("Skipping test for community edition and versions lower than 5.18")

    unauthorized_user = "troygreene"
    expected_message_index = r".*Schema operation.* not allowed for user.*"

    # Node fulltext index
    with pytest.raises(
        ClientError,
        match=expected_message_index,
    ):
        with db.impersonate(unauthorized_user):

            class UnauthorizedFulltextNode(StructuredNode):
                name = StringProperty(fulltext_index=FulltextIndex())

            db.install_labels(UnauthorizedFulltextNode)

    # Node vector index
    with pytest.raises(
        ClientError,
        match=expected_message_index,
    ):
        with db.impersonate(unauthorized_user):

            class UnauthorizedVectorNode(StructuredNode):
                embedding = ArrayProperty(FloatProperty(), vector_index=VectorIndex())

            db.install_labels(UnauthorizedVectorNode)

    # Relationship uniqueness constraint
    with pytest.raises(
        ClientError,
        match=expected_message_index,
    ):
        with db.impersonate(unauthorized_user):

            class UnauthorizedUniqueRel(StructuredRel):
                name = StringProperty(unique_index=True)

            class UnauthorizedUniqueRelNode(StructuredNode):
                has_rel = RelationshipTo(
                    "UnauthorizedUniqueRelNode",
                    "UNAUTHORIZED_UNIQUE_REL",
                    model=UnauthorizedUniqueRel,
                )

            db.install_labels(UnauthorizedUniqueRelNode)

    # Relationship fulltext index
    with pytest.raises(
        ClientError,
        match=expected_message_index,
    ):
        with db.impersonate(unauthorized_user):

            class UnauthorizedFulltextRel(StructuredRel):
                name = StringProperty(fulltext_index=FulltextIndex())

            class UnauthorizedFulltextRelNode(StructuredNode):
                has_rel = RelationshipTo(
                    "UnauthorizedFulltextRelNode",
                    "UNAUTHORIZED_FULLTEXT_REL",
                    model=UnauthorizedFulltextRel,
                )

            db.install_labels(UnauthorizedFulltextRelNode)

    # Relationship vector index
    with pytest.raises(
        ClientError,
        match=expected_message_index,
    ):
        with db.impersonate(unauthorized_user):

            class UnauthorizedVectorRel(StructuredRel):
                embedding = ArrayProperty(FloatProperty(), vector_index=VectorIndex())

            class UnauthorizedVectorRelNode(StructuredNode):
                has_rel = RelationshipTo(
                    "UnauthorizedVectorRelNode",
                    "UNAUTHORIZED_VECTOR_REL",
                    model=UnauthorizedVectorRel,
                )

            db.install_labels(UnauthorizedVectorRelNode)


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
