from datetime import datetime
from test._async_compat import mark_sync_test

import pytest

from neomodel import (
    ArrayProperty,
    DateTimeProperty,
    FloatProperty,
    RelationshipFrom,
    StringProperty,
    StructuredNode,
    StructuredRel,
    VectorIndex,
    db,
)
from neomodel.semantic_filters import VectorFilter


@mark_sync_test
def test_base_vectorfilter():
    """
    Tests that the vectorquery is run, node and score are returned.
    Also tests that if the node property doesnt have a vector index we error.
    """

    # Vector Indexes only exist from 5.13 onwards
    if not db.version_is_higher_than("5.13"):
        pytest.skip("Vector Index not Generally Available in Neo4j.")

    class someNode(StructuredNode):
        name = StringProperty()
        vector = ArrayProperty(
            base_property=FloatProperty(), vector_index=VectorIndex(2, "cosine")
        )

    db.install_labels(someNode)

    john = someNode(name="John", vector=[float(0.5), float(0.5)]).save()
    fred = someNode(name="Fred", vector=[float(1.0), float(0.0)]).save()

    someNodeSearch = someNode.nodes.filter(
        vector_filter=VectorFilter(
            topk=3, vector_attribute_name="vector", candidate_vector=[0.25, 0]
        )
    )
    result = someNodeSearch.all()
    assert all(isinstance(x[0], someNode) for x in result)
    assert all(isinstance(x[1], float) for x in result)

    errorSearch = someNode.nodes.filter(
        vector_filter=VectorFilter(
            topk=3, vector_attribute_name="name", candidate_vector=[0.25, 0]
        )
    )

    with pytest.raises(AttributeError):
        errorSearch.all()


@mark_sync_test
def test_vectorfilter_with_node_propertyfilter():
    """
    Tests that the vector query is run, and "john" node is the only node returned.
    """
    # Vector Indexes only exist from 5.13 onwards
    if not db.version_is_higher_than("5.13"):
        pytest.skip("Vector Index not Generally Available in Neo4j.")

    class someNodeBis(StructuredNode):
        name = StringProperty()
        vector = ArrayProperty(
            base_property=FloatProperty(), vector_index=VectorIndex(2, "cosine")
        )

    db.install_labels(someNodeBis)

    john = someNodeBis(name="John", vector=[float(0.5), float(0.5)]).save()
    fred = someNodeBis(name="Fred", vector=[float(1.0), float(0.0)]).save()

    vectorsearchFilterforJohn = someNodeBis.nodes.filter(
        vector_filter=VectorFilter(
            topk=3, vector_attribute_name="vector", candidate_vector=[0.25, 0]
        ),
        name="John",
    )
    result = vectorsearchFilterforJohn.all()

    assert len(result) == 1
    assert all(isinstance(x[0], someNodeBis) for x in result)
    assert result[0][0].name == "John"
    assert all(isinstance(x[1], float) for x in result)


@mark_sync_test
def test_dont_duplicate_vector_filter_node():
    """
    Tests the situation that another node have the same filter value.
    Testing that we are only perfomring the vectorfilter and metadata filter on the right nodes.
    """
    # Vector Indexes only exist from 5.13 onwards
    if not db.version_is_higher_than("5.13"):
        pytest.skip("Vector Index not Generally Available in Neo4j.")

    class someNodeTer(StructuredNode):
        name = StringProperty()
        vector = ArrayProperty(
            base_property=FloatProperty(), vector_index=VectorIndex(2, "cosine")
        )

    class otherNode(StructuredNode):
        otherName = StringProperty()
        other_vector = ArrayProperty(
            base_property=FloatProperty(), vector_index=VectorIndex(2, "cosine")
        )

    db.install_labels(someNodeTer)
    db.install_labels(otherNode)

    john = someNodeTer(name="John", vector=[float(0.5), float(0.5)]).save()
    fred = someNodeTer(name="Fred", vector=[float(1.0), float(0.0)]).save()
    john2 = otherNode(name="John", vector=[float(0.5), float(0.1)]).save()
    fred2 = otherNode(name="Fred", vector=[float(0.9), float(0.2)]).save()

    john_vector_search = someNodeTer.nodes.filter(
        vector_filter=VectorFilter(
            topk=3, vector_attribute_name="vector", candidate_vector=[0.25, 0]
        ),
        name="John",
    )
    result = john_vector_search.all()

    assert len(result) == 1  # Check we only get the one John
    assert isinstance(result[0][0], someNodeTer)  # check we only get the someNode John
    assert result[0][0].name == "John"
    assert isinstance(result[0][1], float)


@mark_sync_test
def test_django_filter_w_vector_filter():
    """
    Tests that django filters still work with the vector filter on.
    """
    # Vector Indexes only exist from 5.13 onwards
    if not db.version_is_higher_than("5.13"):
        pytest.skip("Vector Index not Generally Available in Neo4j.")

    class djangoNode(StructuredNode):
        name = StringProperty()
        vector = ArrayProperty(
            base_property=FloatProperty(), vector_index=VectorIndex(2, "cosine")
        )
        number = FloatProperty()

    db.install_labels(djangoNode)

    nodeone = djangoNode(
        name="John", vector=[float(0.5), float(0.5)], number=float(10)
    ).save()
    nodetwo = djangoNode(
        name="Fred", vector=[float(0.8), float(0.5)], number=float(3)
    ).save()

    vector_search_with_django_filter = djangoNode.nodes.filter(
        vector_filter=VectorFilter(
            topk=10, vector_attribute_name="vector", candidate_vector=[0.25, 0.25]
        ),
        number__gt=5,
    )
    result = vector_search_with_django_filter.all()
    assert len(result) == 1  # we only get the one node
    assert isinstance(result[0][0], djangoNode)
    assert result[0][0].number > 5


@mark_sync_test
def test_vectorfilter_with_relationshipfilter():
    """
    Tests that by filtering on a vector similarity and then performing a relationshipfilter
    """
    # Vector Indexes only exist from 5.13 onwards
    if not db.version_is_higher_than("5.13"):
        pytest.skip("Vector Index not Generally Available in Neo4j.")

    class SupplierV(StructuredNode):
        name = StringProperty()

    class SuppliesVRel(StructuredRel):
        since = DateTimeProperty(default=datetime.now)

    class ProductV(StructuredNode):
        name = StringProperty()
        description = StringProperty()
        description_embedding = ArrayProperty(
            FloatProperty(), vector_index=VectorIndex(dimensions=2)
        )
        suppliers = RelationshipFrom(SupplierV, "SUPPLIES", model=SuppliesVRel)

    db.install_labels(SupplierV)
    db.install_labels(SuppliesVRel)
    db.install_labels(ProductV)

    supplier1 = SupplierV(name="Supplier 1").save()
    supplier2 = SupplierV(name="Supplier 2").save()
    product1 = ProductV(
        name="Product A",
        description="High quality product",
        description_embedding=[0.1, 0.2],
    ).save()
    product2 = ProductV(
        name="Product B",
        description="High quality product",
        description_embedding=[0.2, 0.2],
    ).save()
    product1.suppliers.connect(supplier1)
    product1.suppliers.connect(supplier2)
    product2.suppliers.connect(supplier1)

    filtered_product = ProductV.nodes.filter(
        vector_filter=VectorFilter(
            topk=1,
            vector_attribute_name="description_embedding",
            candidate_vector=[0.1, 0.1],
        ),
        suppliers__name="Supplier 1",
    )
    result = filtered_product.all()

    assert len(result) == 1
    assert isinstance(result[0][0], ProductV)
    assert isinstance(result[0][1], SupplierV)
    assert isinstance(result[0][2], SuppliesVRel)


@mark_sync_test
def test_vectorfilter_nonexistent_attribute():
    """
    Tests that AttributeError is raised when vector_attribute_name doesn't exist on the source.
    """
    # Vector Indexes only exist from 5.13 onwards
    if not db.version_is_higher_than("5.13"):
        pytest.skip("Vector Index not Generally Available in Neo4j.")

    class TestNodeWithVector(StructuredNode):
        name = StringProperty()
        vector = ArrayProperty(
            base_property=FloatProperty(), vector_index=VectorIndex(2, "cosine")
        )

    db.install_labels(TestNodeWithVector)

    # Test with non-existent attribute name
    with pytest.raises(
        AttributeError, match="Attribute 'nonexistent_vector' not found"
    ):
        nodeset = TestNodeWithVector.nodes.filter(
            vector_filter=VectorFilter(
                topk=3,
                vector_attribute_name="nonexistent_vector",
                candidate_vector=[0.25, 0],
            )
        )
        nodeset.all()  # This triggers the build_vector_query call


@mark_sync_test
def test_vectorfilter_no_vector_index():
    """
    Tests that AttributeError is raised when the attribute exists but doesn't have a vector index.
    """
    # Vector Indexes only exist from 5.13 onwards
    if not db.version_is_higher_than("5.13"):
        pytest.skip("Vector Index not Generally Available in Neo4j.")

    class TestNodeWithoutVector(StructuredNode):
        name = StringProperty()
        vector = ArrayProperty(base_property=FloatProperty())  # No vector_index

    db.install_labels(TestNodeWithoutVector)

    # Test with attribute that exists but has no vector index
    with pytest.raises(AttributeError, match="is not declared with a vector index"):
        nodeset = TestNodeWithoutVector.nodes.filter(
            vector_filter=VectorFilter(
                topk=3, vector_attribute_name="vector", candidate_vector=[0.25, 0]
            )
        )
        nodeset.all()  # This triggers the build_vector_query call
