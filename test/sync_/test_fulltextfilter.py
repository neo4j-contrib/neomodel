from datetime import datetime
from test._async_compat import mark_sync_test

import pytest

from neomodel import (
    DateTimeProperty,
    FloatProperty,
    FulltextIndex,
    RelationshipFrom,
    StringProperty,
    StructuredNode,
    StructuredRel,
    db,
)
from neomodel.semantic_filters import FulltextFilter


@mark_sync_test
def test_base_fulltextfilter():
    """
    Tests that the fulltextquery is run, node and score are returned.
    """

    if not db.version_is_higher_than("5.16"):
        pytest.skip("Not supported before 5.16")

    class fulltextNode(StructuredNode):
        description = StringProperty(
            fulltext_index=FulltextIndex(
                analyzer="standard-no-stop-words", eventually_consistent=False
            )
        )
        other = StringProperty()

    db.install_labels(fulltextNode)

    node1 = fulltextNode(other="thing", description="Another thing").save()

    node2 = fulltextNode(other="other thing", description="Another other thing").save()

    fulltextNodeSearch = fulltextNode.nodes.filter(
        fulltext_filter=FulltextFilter(
            topk=3, fulltext_attribute_name="description", query_string="thing"
        )
    )

    result = fulltextNodeSearch.all()
    assert all(isinstance(x[0], fulltextNode) for x in result)
    assert all(isinstance(x[1], float) for x in result)


@mark_sync_test
def test_fulltextfilter_topk_works():
    """
    Tests that the topk filter works.
    """

    if not db.version_is_higher_than("5.16"):
        pytest.skip("Not supported before 5.16")

    class fulltextNodetopk(StructuredNode):
        description = StringProperty(
            fulltext_index=FulltextIndex(
                analyzer="standard-no-stop-words", eventually_consistent=False
            )
        )

    db.install_labels(fulltextNodetopk)

    node1 = fulltextNodetopk(description="this description").save()
    node2 = fulltextNodetopk(description="that description").save()
    node3 = fulltextNodetopk(description="my description").save()

    fulltextNodeSearch = fulltextNodetopk.nodes.filter(
        fulltext_filter=FulltextFilter(
            topk=2, fulltext_attribute_name="description", query_string="description"
        )
    )

    result = fulltextNodeSearch.all()
    assert len(result) == 2


@mark_sync_test
def test_fulltextfilter_with_node_propertyfilter():
    """
    Tests that the fulltext query is run, and "thing" node is only node returned.
    """

    if not db.version_is_higher_than("5.16"):
        pytest.skip("Not supported before 5.16")

    class fulltextNodeBis(StructuredNode):
        description = StringProperty(
            fulltext_index=FulltextIndex(
                analyzer="standard-no-stop-words", eventually_consistent=False
            )
        )
        other = StringProperty()

    db.install_labels(fulltextNodeBis)

    node1 = fulltextNodeBis(other="thing", description="Another thing").save()

    node2 = fulltextNodeBis(
        other="other thing", description="Another other thing"
    ).save()

    fulltextFilterforthing = fulltextNodeBis.nodes.filter(
        fulltext_filter=FulltextFilter(
            topk=3, fulltext_attribute_name="description", query_string="thing"
        ),
        other="thing",
    )

    result = fulltextFilterforthing.all()

    assert len(result) == 1
    assert all(isinstance(x[0], fulltextNodeBis) for x in result)
    assert result[0][0].other == "thing"
    assert all(isinstance(x[1], float) for x in result)


@mark_sync_test
def test_fulltextfilter_threshold():
    """
    Tests that the fulltext query is run, and only nodes above threshold returns.
    """

    if not db.version_is_higher_than("5.16"):
        pytest.skip("Not supported before 5.16")

    class fulltextNodeThresh(StructuredNode):
        description = StringProperty(
            fulltext_index=FulltextIndex(
                analyzer="standard-no-stop-words", eventually_consistent=False
            )
        )
        other = StringProperty()

    db.install_labels(fulltextNodeThresh)

    node1 = fulltextNodeThresh(other="thing", description="Another thing").save()

    node2 = fulltextNodeThresh(
        other="other thing", description="Another other thing"
    ).save()

    fulltextFilterThresh = fulltextNodeThresh.nodes.filter(
        fulltext_filter=FulltextFilter(
            topk=3,
            fulltext_attribute_name="description",
            query_string="thing",
            threshold=0.09,
        ),
        other="thing",
    )

    result = fulltextFilterThresh.all()

    print(result)
    assert len(result) == 1
    assert all(isinstance(x[0], fulltextNodeThresh) for x in result)
    assert result[0][0].other == "thing"
    assert all(x[1] >= 0.09 for x in result)


@mark_sync_test
def test_dont_duplicate_fulltext_filter_node():
    """
    Tests the situation that another node has the same filter value.
    Testing that we are only performing the fulltextfilter and metadata filter on the right nodes.
    """

    if not db.version_is_higher_than("5.16"):
        pytest.skip("Not supported before 5.16")

    class fulltextNodeTer(StructuredNode):
        description = StringProperty(
            fulltext_index=FulltextIndex(
                analyzer="standard-no-stop-words", eventually_consistent=False
            )
        )
        name = StringProperty()

    class otherfulltextNodeTer(StructuredNode):
        other_description = StringProperty(
            fulltext_index=FulltextIndex(
                analyzer="standard-no-stop-words", eventually_consistent=False
            )
        )
        other_name = StringProperty()

    db.install_labels(fulltextNodeTer)
    db.install_labels(otherfulltextNodeTer)

    node1 = fulltextNodeTer(name="John", description="thing one").save()
    node2 = fulltextNodeTer(name="Fred", description="thing two").save()
    node3 = otherfulltextNodeTer(name="John", description="thing three").save()
    node4 = otherfulltextNodeTer(name="Fred", description="thing four").save()

    john_fulltext_search = fulltextNodeTer.nodes.filter(
        fulltext_filter=FulltextFilter(
            topk=3, fulltext_attribute_name="description", query_string="thing"
        ),
        name="John",
    )

    result = john_fulltext_search.all()

    assert len(result) == 1
    assert isinstance(result[0][0], fulltextNodeTer)
    assert result[0][0].name == "John"
    assert isinstance(result[0][1], float)


@mark_sync_test
def test_django_filter_w_fulltext_filter():
    """
    Tests that django filters still work with the fulltext filter.
    """

    if not db.version_is_higher_than("5.16"):
        pytest.skip("Not supported before 5.16")

    class fulltextDjangoNode(StructuredNode):
        description = StringProperty(
            fulltext_index=FulltextIndex(
                analyzer="standard-no-stop-words", eventually_consistent=False
            )
        )
        name = StringProperty()
        number = FloatProperty()

    db.install_labels(fulltextDjangoNode)

    nodeone = fulltextDjangoNode(
        name="John", description="thing one", number=float(10)
    ).save()

    nodetwo = fulltextDjangoNode(
        name="Fred", description="thing two", number=float(3)
    ).save()

    fulltext_index_with_django_filter = fulltextDjangoNode.nodes.filter(
        fulltext_filter=FulltextFilter(
            topk=3, fulltext_attribute_name="description", query_string="thing"
        ),
        number__gt=5,
    )

    result = fulltext_index_with_django_filter.all()
    assert len(result) == 1
    assert isinstance(result[0][0], fulltextDjangoNode)
    assert result[0][0].number > 5


@mark_sync_test
def test_fulltextfilter_with_relationshipfilter():
    """
    Tests that by filtering on fulltext similarity and then peforming a relationshipfilter works.
    """

    if not db.version_is_higher_than("5.16"):
        pytest.skip("Not supported before 5.16")

    class SupplierFT(StructuredNode):
        name = StringProperty()

    class SuppliesFTRel(StructuredRel):
        since = DateTimeProperty(default=datetime.now)

    class ProductFT(StructuredNode):
        name = StringProperty()
        description = StringProperty(
            fulltext_index=FulltextIndex(
                analyzer="standard-no-stop-words", eventually_consistent=False
            )
        )
        suppliers = RelationshipFrom(SupplierFT, "SUPPLIES", model=SuppliesFTRel)

    db.install_labels(SupplierFT)
    db.install_labels(SuppliesFTRel)
    db.install_labels(ProductFT)

    supplier1 = SupplierFT(name="Supplier 1").save()
    supplier2 = SupplierFT(name="Supplier 2").save()
    product1 = ProductFT(
        name="Product A",
        description="High quality product",
    ).save()
    product2 = ProductFT(
        name="Product B",
        description="Very High quality product",
    ).save()
    product1.suppliers.connect(supplier1)
    product1.suppliers.connect(supplier2)
    product2.suppliers.connect(supplier1)

    filtered_product = ProductFT.nodes.filter(
        fulltext_filter=FulltextFilter(
            topk=1, fulltext_attribute_name="description", query_string="product"
        ),
        suppliers__name="Supplier 1",
    )

    result = filtered_product.all()

    assert len(result) == 1
    assert isinstance(result[0][0], ProductFT)
    assert isinstance(result[0][1], SupplierFT)
    assert isinstance(result[0][2], SuppliesFTRel)


@mark_sync_test
def test_fulltextfiler_nonexistent_attribute():
    """
    Tests that AttributeError is raised when fulltext_attribute_name doesn't exist on the source.
    """

    if not db.version_is_higher_than("5.16"):
        pytest.skip("Not supported before 5.16")

    class TestNodeWithFT(StructuredNode):
        name = StringProperty()
        fulltext = StringProperty(
            fulltext_index=FulltextIndex(
                analyzer="standard-no-stop-words", eventually_consistent=False
            )
        )

    db.install_labels(TestNodeWithFT)

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
        nodeset.all()


@mark_sync_test
def test_fulltextfiler_no_fulltext_index():
    """
    Tests that AttributeError is raised when fulltext_attribute_name doesn't exist on the source.
    """

    if not db.version_is_higher_than("5.16"):
        pytest.skip("Not supported before 5.16")

    class TestNodeWithoutFT(StructuredNode):
        name = StringProperty()
        fulltext = StringProperty()  # No fulltext_index

    db.install_labels(TestNodeWithoutFT)

    with pytest.raises(AttributeError, match="is not declared with a full text index"):
        nodeset = TestNodeWithoutFT.nodes.filter(
            fulltext_filter=FulltextFilter(
                topk=1, fulltext_attribute_name="fulltext", query_string="something"
            )
        )
        nodeset.all()
