from datetime import datetime
from test._async_compat import mark_async_test

import pytest

from neomodel import (
    AsyncRelationshipFrom,
    AsyncStructuredNode,
    AsyncStructuredRel,
    DateTimeProperty,
    FloatProperty,
    StringProperty,
    FulltextIndex,
    adb,
)
from neomodel.semantic_filters import FulltextFilter


@mark_async_test
async def test_base_fulltextfilter():
    """
    Tests that the fulltextquery is run, node and score are returned.
    """

    if not await adb.version_is_higher_than("5.16"):
        pytest.skip("Not supported before 5.16")

    class fulltextNode(AsyncStructuredNode):
        description = StringProperty(
            fulltext_index=FulltextIndex(
                analyzer="standard-no-stop-words", eventually_consistent=False
            )
        )
        other = StringProperty()

    await adb.install_labels(fulltextNode)

    node1 = await fulltextNode(other="thing", description="Another thing").save()

    node2 = await fulltextNode(
        other="other thing", description="Another other thing"
    ).save()

    fulltextNodeSearch = fulltextNode.nodes.filter(
        fulltext_filter=FulltextFilter(
            topk=3, fulltext_attribute_name="description", query_string="thing"
        )
    )

    result = await fulltextNodeSearch.all()
    print(result)
    assert all(isinstance(x[0], fulltextNode) for x in result)
    assert all(isinstance(x[1], float) for x in result)


@mark_async_test
async def test_fulltextfilter_with_node_propertyfilter():
    """
    Tests that the fulltext query is run, and "thing" node is only node returned.
    """

    class fulltextNodeBis(AsyncStructuredNode):
        description = StringProperty(
            fulltext_index=FulltextIndex(
                analyzer="standard-no-stop-words", eventually_consistent=False
            )
        )
        other = StringProperty()

    await adb.install_labels(fulltextNodeBis)

    node1 = await fulltextNodeBis(other="thing", description="Another thing").save()

    node2 = await fulltextNodeBis(
        other="other thing", description="Another other thing"
    ).save()

    fulltextFilterforthing = fulltextNodeBis.nodes.filter(
        fulltext_filter=FulltextFilter(
            topk=3, fulltext_attribute_name="description", query_string="thing"
        ),
        other="thing",
    )

    result = await fulltextFilterforthing.all()

    assert len(result) == 1
    assert all(isinstance(x[0], fulltextNodeBis) for x in result)
    assert result[0][0].other == "thing"
    assert all(isinstance(x[1], float) for x in result)


@mark_async_test
async def test_dont_duplicate_fulltext_filter_node():
    """
    Tests the situation that another node has the same filter value.
    Testing that we are only performing the fulltextfilter and metadata filter on the right nodes.
    """

    if not await adb.version_is_higher_than("5.16"):
        pytest.skip("Not supported before 5.16")

    class fulltextNodeTer(AsyncStructuredNode):
        description = StringProperty(
            fulltext_index=FulltextIndex(
                analyzer="standard-no-stop-words", eventually_consistent=False
            )
        )
        name = StringProperty()

    class otherfulltextNodeTer(AsyncStructuredNode):
        other_description = StringProperty(
            fulltext_index=FulltextIndex(
                analyzer="standard-no-stop-words", eventually_consistent=False
            )
        )
        other_name = StringProperty()

    await adb.install_labels(fulltextNodeTer)
    await adb.install_labels(otherfulltextNodeTer)

    node1 = await fulltextNodeTer(name="John", description="thing one").save()
    node2 = await fulltextNodeTer(name="Fred", description="thing two").save()
    node3 = await otherfulltextNodeTer(name="John", description="thing three").save()
    node4 = await otherfulltextNodeTer(name="Fred", description="thing four").save()

    john_fulltext_search = fulltextNodeTer.nodes.filter(
        fulltext_filter=FulltextFilter(
            topk=3, fulltext_attribute_name="description", query_string="thing"
        ),
        name="John",
    )

    result = await john_fulltext_search.all()

    assert len(result) == 1
    assert isinstance(result[0][0], fulltextNodeTer)
    assert result[0][0].name == "John"
    assert isinstance(result[0][1], float)


@mark_async_test
async def test_django_filter_w_fulltext_filter():
    """
    Tests that django filters still work with the fulltext filter.
    """

    if not await adb.version_is_higher_than("5.16"):
        pytest.skip("Not supported before 5.16")

    class fulltextDjangoNode(AsyncStructuredNode):
        description = StringProperty(
            fulltext_index=FulltextIndex(
                analyzer="standard-no-stop-words", eventually_consistent=False
            )
        )
        name = StringProperty()
        number = FloatProperty()

    await adb.install_labels(fulltextDjangoNode)

    nodeone = await fulltextDjangoNode(
        name="John", description="thing one", number=float(10)
    ).save()

    nodetwo = await fulltextDjangoNode(
        name="Fred", description="thing two", number=float(3)
    ).save()

    fulltext_index_with_django_filter = fulltextDjangoNode.nodes.filter(
        fulltext_filter=FulltextFilter(
            topk=3, fulltext_attribute_name="description", query_string="thing"
        ),
        number__gt=5,
    )

    result = await fulltext_index_with_django_filter.all()
    assert len(result) == 1
    assert isinstance(result[0][0], fulltextDjangoNode)
    assert result[0][0].number > 5


@mark_async_test
async def test_fulltextfilter_with_relationshipfilter():
    """
    Tests that by filtering on fulltext similarity and then peforming a relationshipfilter works.
    """

    if not await adb.version_is_higher_than("5.16"):
        pytest.skip("Not supported before 5.16")

    class SupplierFT(AsyncStructuredNode):
        name = StringProperty()

    class SuppliesFTRel(AsyncStructuredRel):
        since = DateTimeProperty(default=datetime.now)

    class ProductFT(AsyncStructuredNode):
        name = StringProperty()
        description = StringProperty(
            fulltext_index=FulltextIndex(
                analyzer="standard-no-stop-words", eventually_consistent=False
            )
        )
        suppliers = AsyncRelationshipFrom(SupplierFT, "SUPPLIES", model=SuppliesFTRel)

    await adb.install_labels(SupplierFT)
    await adb.install_labels(SuppliesFTRel)
    await adb.install_labels(ProductFT)

    supplier1 = await SupplierFT(name="Supplier 1").save()
    supplier2 = await SupplierFT(name="Supplier 2").save()
    product1 = await ProductFT(
        name="Product A",
        description="High quality product",
    ).save()
    product2 = await ProductFT(
        name="Product B",
        description="Very High quality product",
    ).save()
    await product1.suppliers.connect(supplier1)
    await product1.suppliers.connect(supplier2)
    await product2.suppliers.connect(supplier1)

    filtered_product = ProductFT.nodes.filter(
        fulltext_filter=FulltextFilter(
            topk=1, fulltext_attribute_name="description", query_string="product"
        ),
        suppliers__name="Supplier 1",
    )

    result = await filtered_product.all()

    assert len(result) == 1
    assert isinstance(result[0][0], ProductFT)
    assert isinstance(result[0][1], SupplierFT)
    assert isinstance(result[0][2], SuppliesFTRel)


@mark_async_test
async def test_fulltextfiler_nonexistent_attribute():
    """
    Tests that AttributeError is raised when fulltext_attribute_name doesn't exist on the source.
    """

    class TestNodeWithFT(AsyncStructuredNode):
        name = StringProperty()
        fulltext = StringProperty(
            fulltext_index=FulltextIndex(
                analyzer="standard-no-stop-words", eventually_consistent=False
            )
        )

    await adb.install_labels(TestNodeWithFT)

    with pytest.raises(
        AttributeError, match="Atribute 'nonexistent_fulltext' not found"
    ):
        nodeset = TestNodeWithFT.nodes.filter(
            fulltext_filter=FulltextFilter(
                topk=1,
                fulltext_attribute_name="nonexistent_fulltext",
                query_string="something",
            )
        )
        await nodeset.all()


@mark_async_test
async def test_fulltextfiler_no_fulltext_index():
    """
    Tests that AttributeError is raised when fulltext_attribute_name doesn't exist on the source.
    """

    class TestNodeWithoutFT(AsyncStructuredNode):
        name = StringProperty()
        fulltext = StringProperty()  # No fulltext_index

    await adb.install_labels(TestNodeWithoutFT)

    with pytest.raises(AttributeError, match="is not declared with a full text index"):
        nodeset = TestNodeWithoutFT.nodes.filter(
            fulltext_filter=FulltextFilter(
                topk=1, fulltext_attribute_name="fulltext", query_string="something"
            )
        )
        await nodeset.all()
