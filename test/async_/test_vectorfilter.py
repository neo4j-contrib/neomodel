from datetime import datetime
from test._async_compat import mark_async_test

import pytest

from neomodel import (
    ArrayProperty,
    AsyncRelationshipFrom,
    AsyncStructuredNode,
    AsyncStructuredRel,
    DateTimeProperty,
    FloatProperty,
    StringProperty,
    VectorIndex,
    adb,
)
from neomodel.semantic_filters import VectorFilter


@mark_async_test
async def test_base_vectorfilter():
    """
    Tests that the vectorquery is run, node and score are returned.
    """

    # Vector Indexes only exist from 5.13 onwards
    if not await adb.version_is_higher_than("5.13"):
        pytest.skip("Vector Index not Generally Available in Neo4j.")

    class someNode(AsyncStructuredNode):
        name = StringProperty()
        vector = ArrayProperty(
            base_property=FloatProperty(), vector_index=VectorIndex(2, "cosine")
        )

    await adb.install_labels(someNode)

    john = await someNode(name="John", vector=[float(0.5), float(0.5)]).save()
    fred = await someNode(name="Fred", vector=[float(1.0), float(0.0)]).save()

    someNodeSearch = someNode.nodes.filter(
        vector_filter=VectorFilter(
            topk=3, vector_attribute_name="vector", candidate_vector=[0.25, 0]
        )
    )
    result = await someNodeSearch.all()
    assert all(isinstance(x[0], someNode) for x in result)
    assert all(isinstance(x[1], float) for x in result)

    errorSearch = someNode.nodes.filter(
        vector_filter=VectorFilter(
            topk=3, vector_attribute_name="name", candidate_vector=[0.25, 0]
        )
    )

    with pytest.raises(AttributeError):
        await errorSearch.all()


@mark_async_test
async def test_vectorfilter_with_node_propertyfilter():
    """
    Tests that the vector query is run, and "john" node is the only node returned.
    """
    # Vector Indexes only exist from 5.13 onwards
    if not await adb.version_is_higher_than("5.13"):
        pytest.skip("Vector Index not Generally Available in Neo4j.")

    class someNodeBis(AsyncStructuredNode):
        name = StringProperty()
        vector = ArrayProperty(
            base_property=FloatProperty(), vector_index=VectorIndex(2, "cosine")
        )

    await adb.install_labels(someNodeBis)

    john = await someNodeBis(name="John", vector=[float(0.5), float(0.5)]).save()
    fred = await someNodeBis(name="Fred", vector=[float(1.0), float(0.0)]).save()

    vectorsearchFilterforJohn = someNodeBis.nodes.filter(
        vector_filter=VectorFilter(
            topk=3, vector_attribute_name="vector", candidate_vector=[0.25, 0]
        ),
        name="John",
    )
    result = await vectorsearchFilterforJohn.all()

    assert len(result) == 1
    assert all(isinstance(x[0], someNodeBis) for x in result)
    assert result[0][0].name == "John"
    assert all(isinstance(x[1], float) for x in result)


@mark_async_test
async def test_dont_duplicate_vector_filter_node():
    """
    Tests the situation that another node has the same filter value.
    Testing that we are only perfomring the vectorfilter and metadata filter on the right nodes.
    """
    # Vector Indexes only exist from 5.13 onwards
    if not await adb.version_is_higher_than("5.13"):
        pytest.skip("Vector Index not Generally Available in Neo4j.")

    class someNodeTer(AsyncStructuredNode):
        name = StringProperty()
        vector = ArrayProperty(
            base_property=FloatProperty(), vector_index=VectorIndex(2, "cosine")
        )

    class otherNode(AsyncStructuredNode):
        otherName = StringProperty()
        other_vector = ArrayProperty(
            base_property=FloatProperty(), vector_index=VectorIndex(2, "cosine")
        )

    await adb.install_labels(someNodeTer)
    await adb.install_labels(otherNode)

    john = await someNodeTer(name="John", vector=[float(0.5), float(0.5)]).save()
    fred = await someNodeTer(name="Fred", vector=[float(1.0), float(0.0)]).save()
    john2 = await otherNode(name="John", vector=[float(0.5), float(0.1)]).save()
    fred2 = await otherNode(name="Fred", vector=[float(0.9), float(0.2)]).save()

    john_vector_search = someNodeTer.nodes.filter(
        vector_filter=VectorFilter(
            topk=3, vector_attribute_name="vector", candidate_vector=[0.25, 0]
        ),
        name="John",
    )
    result = await john_vector_search.all()

    assert len(result) == 1  # Check we only get the one John
    assert isinstance(result[0][0], someNodeTer)  # check we only get the someNode John
    assert result[0][0].name == "John"
    assert isinstance(result[0][1], float)


@mark_async_test
async def test_django_filter_w_vector_filter():
    """
    Tests that django filters still work with the vector filter.
    """
    # Vector Indexes only exist from 5.13 onwards
    if not await adb.version_is_higher_than("5.13"):
        pytest.skip("Vector Index not Generally Available in Neo4j.")

    class djangoNode(AsyncStructuredNode):
        name = StringProperty()
        vector = ArrayProperty(
            base_property=FloatProperty(), vector_index=VectorIndex(2, "cosine")
        )
        number = FloatProperty()

    await adb.install_labels(djangoNode)

    nodeone = await djangoNode(
        name="John", vector=[float(0.5), float(0.5)], number=float(10)
    ).save()
    nodetwo = await djangoNode(
        name="Fred", vector=[float(0.8), float(0.5)], number=float(3)
    ).save()

    vector_search_with_django_filter = djangoNode.nodes.filter(
        vector_filter=VectorFilter(
            topk=10, vector_attribute_name="vector", candidate_vector=[0.25, 0.25]
        ),
        number__gt=5,
    )
    result = await vector_search_with_django_filter.all()
    assert len(result) == 1  # we only get the one node
    assert isinstance(result[0][0], djangoNode)
    assert result[0][0].number > 5


@mark_async_test
async def test_vectorfilter_with_relationshipfilter():
    """
    Tests that by filtering on a vector similarity and then performing a relationshipfilter works.
    """
    # Vector Indexes only exist from 5.13 onwards
    if not await adb.version_is_higher_than("5.13"):
        pytest.skip("Vector Index not Generally Available in Neo4j.")

    class SupplierV(AsyncStructuredNode):
        name = StringProperty()

    class SuppliesVRel(AsyncStructuredRel):
        since = DateTimeProperty(default=datetime.now)

    class ProductV(AsyncStructuredNode):
        name = StringProperty()
        description = StringProperty()
        description_embedding = ArrayProperty(
            FloatProperty(), vector_index=VectorIndex(dimensions=2)
        )
        suppliers = AsyncRelationshipFrom(SupplierV, "SUPPLIES", model=SuppliesVRel)

    await adb.install_labels(SupplierV)
    await adb.install_labels(SuppliesVRel)
    await adb.install_labels(ProductV)

    supplier1 = await SupplierV(name="Supplier 1").save()
    supplier2 = await SupplierV(name="Supplier 2").save()
    product1 = await ProductV(
        name="Product A",
        description="High quality product",
        description_embedding=[0.1, 0.2],
    ).save()
    product2 = await ProductV(
        name="Product B",
        description="High quality product",
        description_embedding=[0.2, 0.2],
    ).save()
    await product1.suppliers.connect(supplier1)
    await product1.suppliers.connect(supplier2)
    await product2.suppliers.connect(supplier1)

    filtered_product = ProductV.nodes.filter(
        vector_filter=VectorFilter(
            topk=1,
            vector_attribute_name="description_embedding",
            candidate_vector=[0.1, 0.1],
        ),
        suppliers__name="Supplier 1",
    )
    result = await filtered_product.all()

    assert len(result) == 1
    assert isinstance(result[0][0], ProductV)
    assert isinstance(result[0][1], SupplierV)
    assert isinstance(result[0][2], SuppliesVRel)
