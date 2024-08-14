from datetime import datetime
from test._async_compat import mark_async_test

from pytest import raises

from neomodel import (
    INCOMING,
    ArrayProperty,
    AsyncRelationshipFrom,
    AsyncRelationshipTo,
    AsyncStructuredNode,
    AsyncStructuredRel,
    DateTimeProperty,
    IntegerProperty,
    Q,
    StringProperty,
    UniqueIdProperty,
)
from neomodel._async_compat.util import AsyncUtil
from neomodel.async_.match import (
    AsyncNodeSet,
    AsyncQueryBuilder,
    AsyncTraversal,
    Optional,
)
from neomodel.exceptions import MultipleNodesReturned, RelationshipClassNotDefined


class SupplierRel(AsyncStructuredRel):
    since = DateTimeProperty(default=datetime.now)
    courier = StringProperty()


class Supplier(AsyncStructuredNode):
    name = StringProperty()
    delivery_cost = IntegerProperty()
    coffees = AsyncRelationshipTo("Coffee", "COFFEE SUPPLIERS")


class Species(AsyncStructuredNode):
    name = StringProperty()
    tags = ArrayProperty(StringProperty(), default=list)
    coffees = AsyncRelationshipFrom(
        "Coffee", "COFFEE SPECIES", model=AsyncStructuredRel
    )


class Coffee(AsyncStructuredNode):
    name = StringProperty(unique_index=True)
    price = IntegerProperty()
    suppliers = AsyncRelationshipFrom(Supplier, "COFFEE SUPPLIERS", model=SupplierRel)
    species = AsyncRelationshipTo(Species, "COFFEE SPECIES", model=AsyncStructuredRel)
    id_ = IntegerProperty()


class Extension(AsyncStructuredNode):
    extension = AsyncRelationshipTo("Extension", "extension")


class CountryX(AsyncStructuredNode):
    code = StringProperty(unique_index=True, required=True)
    inhabitant = AsyncRelationshipFrom("PersonX", "IS_FROM")


class CityX(AsyncStructuredNode):
    name = StringProperty(required=True)
    country = AsyncRelationshipTo(CountryX, "FROM_COUNTRY")


class PersonX(AsyncStructuredNode):
    uid = UniqueIdProperty()
    name = StringProperty(unique_index=True)
    age = IntegerProperty(index=True, default=0)

    # traverse outgoing IS_FROM relations, inflate to Country objects
    country = AsyncRelationshipTo(CountryX, "IS_FROM")

    # traverse outgoing LIVES_IN relations, inflate to City objects
    city = AsyncRelationshipTo(CityX, "LIVES_IN")


@mark_async_test
async def test_filter_exclude_via_labels():
    await Coffee(name="Java", price=99).save()

    node_set = AsyncNodeSet(Coffee)
    qb = await AsyncQueryBuilder(node_set).build_ast()

    results = [node async for node in qb._execute()]

    assert "(coffee:Coffee)" in qb._ast.match
    assert qb._ast.result_class
    assert len(results) == 1
    assert isinstance(results[0], Coffee)
    assert results[0].name == "Java"

    # with filter and exclude
    await Coffee(name="Kenco", price=3).save()
    node_set = node_set.filter(price__gt=2).exclude(price__gt=6, name="Java")
    qb = await AsyncQueryBuilder(node_set).build_ast()

    results = [node async for node in qb._execute()]
    assert "(coffee:Coffee)" in qb._ast.match
    assert "NOT" in qb._ast.where[0]
    assert len(results) == 1
    assert results[0].name == "Kenco"


@mark_async_test
async def test_simple_has_via_label():
    nescafe = await Coffee(name="Nescafe", price=99).save()
    tesco = await Supplier(name="Tesco", delivery_cost=2).save()
    await nescafe.suppliers.connect(tesco)

    ns = AsyncNodeSet(Coffee).has(suppliers=True)
    qb = await AsyncQueryBuilder(ns).build_ast()
    results = [node async for node in qb._execute()]
    assert "COFFEE SUPPLIERS" in qb._ast.where[0]
    assert len(results) == 1
    assert results[0].name == "Nescafe"

    await Coffee(name="nespresso", price=99).save()
    ns = AsyncNodeSet(Coffee).has(suppliers=False)
    qb = await AsyncQueryBuilder(ns).build_ast()
    results = [node async for node in qb._execute()]
    assert len(results) > 0
    assert "NOT" in qb._ast.where[0]


@mark_async_test
async def test_get():
    await Coffee(name="1", price=3).save()
    assert await Coffee.nodes.get(name="1")

    with raises(Coffee.DoesNotExist):
        await Coffee.nodes.get(name="2")

    await Coffee(name="2", price=3).save()

    with raises(MultipleNodesReturned):
        await Coffee.nodes.get(price=3)


@mark_async_test
async def test_simple_traverse_with_filter():
    nescafe = await Coffee(name="Nescafe2", price=99).save()
    tesco = await Supplier(name="Sainsburys", delivery_cost=2).save()
    await nescafe.suppliers.connect(tesco)

    qb = AsyncQueryBuilder(
        AsyncNodeSet(source=nescafe).suppliers.match(since__lt=datetime.now())
    )

    _ast = await qb.build_ast()
    results = [node async for node in qb._execute()]

    assert qb._ast.lookup
    assert qb._ast.match
    assert qb._ast.return_clause.startswith("suppliers")
    assert len(results) == 1
    assert results[0].name == "Sainsburys"


@mark_async_test
async def test_double_traverse():
    nescafe = await Coffee(name="Nescafe plus", price=99).save()
    tesco = await Supplier(name="Asda", delivery_cost=2).save()
    await nescafe.suppliers.connect(tesco)
    await tesco.coffees.connect(await Coffee(name="Decafe", price=2).save())

    ns = AsyncNodeSet(AsyncNodeSet(source=nescafe).suppliers.match()).coffees.match()
    qb = await AsyncQueryBuilder(ns).build_ast()

    results = [node async for node in qb._execute()]
    assert len(results) == 2
    names = [n.name for n in results]
    assert "Decafe" in names
    assert "Nescafe plus" in names


@mark_async_test
async def test_count():
    await Coffee(name="Nescafe Gold", price=99).save()
    ast = await AsyncQueryBuilder(AsyncNodeSet(source=Coffee)).build_ast()
    count = await ast._count()
    assert count > 0

    await Coffee(name="Kawa", price=27).save()
    node_set = AsyncNodeSet(source=Coffee)
    node_set.skip = 1
    node_set.limit = 1
    ast = await AsyncQueryBuilder(node_set).build_ast()
    count = await ast._count()
    assert count == 1


@mark_async_test
async def test_len_and_iter_and_bool():
    iterations = 0

    await Coffee(name="Icelands finest").save()

    for c in await Coffee.nodes:
        iterations += 1
        await c.delete()

    assert iterations > 0

    assert len(await Coffee.nodes) == 0


@mark_async_test
async def test_slice():
    for c in await Coffee.nodes:
        await c.delete()

    await Coffee(name="Icelands finest").save()
    await Coffee(name="Britains finest").save()
    await Coffee(name="Japans finest").save()

    # Branching tests because async needs extra brackets
    if AsyncUtil.is_async_code:
        assert len(list((await Coffee.nodes)[1:])) == 2
        assert len(list((await Coffee.nodes)[:1])) == 1
        assert isinstance((await Coffee.nodes)[1], Coffee)
        assert isinstance((await Coffee.nodes)[0], Coffee)
        assert len(list((await Coffee.nodes)[1:2])) == 1
    else:
        assert len(list(Coffee.nodes[1:])) == 2
        assert len(list(Coffee.nodes[:1])) == 1
        assert isinstance(Coffee.nodes[1], Coffee)
        assert isinstance(Coffee.nodes[0], Coffee)
        assert len(list(Coffee.nodes[1:2])) == 1


@mark_async_test
async def test_issue_208():
    # calls to match persist across queries.

    b = await Coffee(name="basics").save()
    l = await Supplier(name="lidl").save()
    a = await Supplier(name="aldi").save()

    await b.suppliers.connect(l, {"courier": "fedex"})
    await b.suppliers.connect(a, {"courier": "dhl"})

    assert len(await b.suppliers.match(courier="fedex"))
    assert len(await b.suppliers.match(courier="dhl"))


@mark_async_test
async def test_issue_589():
    node1 = await Extension().save()
    node2 = await Extension().save()
    assert node2 not in await node1.extension
    await node1.extension.connect(node2)
    assert node2 in await node1.extension


@mark_async_test
async def test_contains():
    expensive = await Coffee(price=1000, name="Pricey").save()
    asda = await Coffee(name="Asda", price=1).save()

    assert expensive in await Coffee.nodes.filter(price__gt=999)
    assert asda not in await Coffee.nodes.filter(price__gt=999)

    # bad value raises
    with raises(ValueError, match=r"Expecting StructuredNode instance"):
        if AsyncUtil.is_async_code:
            assert await Coffee.nodes.check_contains(2)
        else:
            assert 2 in Coffee.nodes

    # unsaved
    with raises(ValueError, match=r"Unsaved node"):
        if AsyncUtil.is_async_code:
            assert await Coffee.nodes.check_contains(Coffee())
        else:
            assert Coffee() in Coffee.nodes


@mark_async_test
async def test_order_by():
    for c in await Coffee.nodes:
        await c.delete()

    c1 = await Coffee(name="Icelands finest", price=5).save()
    c2 = await Coffee(name="Britains finest", price=10).save()
    c3 = await Coffee(name="Japans finest", price=35).save()

    if AsyncUtil.is_async_code:
        assert ((await Coffee.nodes.order_by("price"))[0]).price == 5
        assert ((await Coffee.nodes.order_by("-price"))[0]).price == 35
    else:
        assert (Coffee.nodes.order_by("price")[0]).price == 5
        assert (Coffee.nodes.order_by("-price")[0]).price == 35

    ns = Coffee.nodes.order_by("-price")
    qb = await AsyncQueryBuilder(ns).build_ast()
    assert qb._ast.order_by
    ns = ns.order_by(None)
    qb = await AsyncQueryBuilder(ns).build_ast()
    assert not qb._ast.order_by
    ns = ns.order_by("?")
    qb = await AsyncQueryBuilder(ns).build_ast()
    assert qb._ast.with_clause == "coffee, rand() as r"
    assert qb._ast.order_by == "r"

    with raises(
        ValueError,
        match=r".*Neo4j internals like id or element_id are not allowed for use in this operation.",
    ):
        await Coffee.nodes.order_by("id")

    # Test order by on a relationship
    l = await Supplier(name="lidl2").save()
    await l.coffees.connect(c1)
    await l.coffees.connect(c2)
    await l.coffees.connect(c3)

    ordered_n = [n for n in await l.coffees.order_by("name")]
    assert ordered_n[0] == c2
    assert ordered_n[1] == c1
    assert ordered_n[2] == c3


@mark_async_test
async def test_extra_filters():
    for c in await Coffee.nodes:
        await c.delete()

    c1 = await Coffee(name="Icelands finest", price=5, id_=1).save()
    c2 = await Coffee(name="Britains finest", price=10, id_=2).save()
    c3 = await Coffee(name="Japans finest", price=35, id_=3).save()
    c4 = await Coffee(name="US extra-fine", price=None, id_=4).save()

    coffees_5_10 = await Coffee.nodes.filter(price__in=[10, 5])
    assert len(coffees_5_10) == 2, "unexpected number of results"
    assert c1 in coffees_5_10, "doesnt contain 5 price coffee"
    assert c2 in coffees_5_10, "doesnt contain 10 price coffee"

    finest_coffees = await Coffee.nodes.filter(name__iendswith=" Finest")
    assert len(finest_coffees) == 3, "unexpected number of results"
    assert c1 in finest_coffees, "doesnt contain 1st finest coffee"
    assert c2 in finest_coffees, "doesnt contain 2nd finest coffee"
    assert c3 in finest_coffees, "doesnt contain 3rd finest coffee"

    unpriced_coffees = await Coffee.nodes.filter(price__isnull=True)
    assert len(unpriced_coffees) == 1, "unexpected number of results"
    assert c4 in unpriced_coffees, "doesnt contain unpriced coffee"

    coffees_with_id_gte_3 = await Coffee.nodes.filter(id___gte=3)
    assert len(coffees_with_id_gte_3) == 2, "unexpected number of results"
    assert c3 in coffees_with_id_gte_3
    assert c4 in coffees_with_id_gte_3

    with raises(
        ValueError,
        match=r".*Neo4j internals like id or element_id are not allowed for use in this operation.",
    ):
        await Coffee.nodes.filter(elementId="4:xxx:111").all()


def test_traversal_definition_keys_are_valid():
    muckefuck = Coffee(name="Mukkefuck", price=1)

    with raises(ValueError):
        AsyncTraversal(
            muckefuck,
            "a_name",
            {
                "node_class": Supplier,
                "direction": INCOMING,
                "relationship_type": "KNOWS",
                "model": None,
            },
        )

    AsyncTraversal(
        muckefuck,
        "a_name",
        {
            "node_class": Supplier,
            "direction": INCOMING,
            "relation_type": "KNOWS",
            "model": None,
        },
    )


@mark_async_test
async def test_empty_filters():
    """Test this case:
     ```
         SomeModel.nodes.filter().filter(Q(arg1=val1)).all()
         SomeModel.nodes.exclude().exclude(Q(arg1=val1)).all()
         SomeModel.nodes.filter().filter(arg1=val1).all()
    ```
    In django_rest_framework filter uses such as lazy function and
    ``get_queryset`` function in ``GenericAPIView`` should returns
    ``NodeSet`` object.
    """

    for c in await Coffee.nodes:
        await c.delete()

    c1 = await Coffee(name="Super", price=5, id_=1).save()
    c2 = await Coffee(name="Puper", price=10, id_=2).save()

    empty_filter = Coffee.nodes.filter()

    all_coffees = await empty_filter.all()
    assert len(all_coffees) == 2, "unexpected number of results"

    filter_empty_filter = empty_filter.filter(price=5)
    assert len(await filter_empty_filter.all()) == 1, "unexpected number of results"
    assert (
        c1 in await filter_empty_filter.all()
    ), "doesnt contain c1 in ``filter_empty_filter``"

    filter_q_empty_filter = empty_filter.filter(Q(price=5))
    assert len(await filter_empty_filter.all()) == 1, "unexpected number of results"
    assert (
        c1 in await filter_empty_filter.all()
    ), "doesnt contain c1 in ``filter_empty_filter``"


@mark_async_test
async def test_q_filters():
    # Test where no children and self.connector != conn ?
    for c in await Coffee.nodes:
        await c.delete()

    c1 = await Coffee(name="Icelands finest", price=5, id_=1).save()
    c2 = await Coffee(name="Britains finest", price=10, id_=2).save()
    c3 = await Coffee(name="Japans finest", price=35, id_=3).save()
    c4 = await Coffee(name="US extra-fine", price=None, id_=4).save()
    c5 = await Coffee(name="Latte", price=35, id_=5).save()
    c6 = await Coffee(name="Cappuccino", price=35, id_=6).save()

    coffees_5_10 = await Coffee.nodes.filter(Q(price=10) | Q(price=5)).all()
    assert len(coffees_5_10) == 2, "unexpected number of results"
    assert c1 in coffees_5_10, "doesnt contain 5 price coffee"
    assert c2 in coffees_5_10, "doesnt contain 10 price coffee"

    coffees_5_6 = (
        await Coffee.nodes.filter(Q(name="Latte") | Q(name="Cappuccino"))
        .filter(price=35)
        .all()
    )
    assert len(coffees_5_6) == 2, "unexpected number of results"
    assert c5 in coffees_5_6, "doesnt contain 5 coffee"
    assert c6 in coffees_5_6, "doesnt contain 6 coffee"

    coffees_5_6 = (
        await Coffee.nodes.filter(price=35)
        .filter(Q(name="Latte") | Q(name="Cappuccino"))
        .all()
    )
    assert len(coffees_5_6) == 2, "unexpected number of results"
    assert c5 in coffees_5_6, "doesnt contain 5 coffee"
    assert c6 in coffees_5_6, "doesnt contain 6 coffee"

    finest_coffees = await Coffee.nodes.filter(name__iendswith=" Finest").all()
    assert len(finest_coffees) == 3, "unexpected number of results"
    assert c1 in finest_coffees, "doesnt contain 1st finest coffee"
    assert c2 in finest_coffees, "doesnt contain 2nd finest coffee"
    assert c3 in finest_coffees, "doesnt contain 3rd finest coffee"

    unpriced_coffees = await Coffee.nodes.filter(Q(price__isnull=True)).all()
    assert len(unpriced_coffees) == 1, "unexpected number of results"
    assert c4 in unpriced_coffees, "doesnt contain unpriced coffee"

    coffees_with_id_gte_3 = await Coffee.nodes.filter(Q(id___gte=3)).all()
    assert len(coffees_with_id_gte_3) == 4, "unexpected number of results"
    assert c3 in coffees_with_id_gte_3
    assert c4 in coffees_with_id_gte_3
    assert c5 in coffees_with_id_gte_3
    assert c6 in coffees_with_id_gte_3

    coffees_5_not_japans = await Coffee.nodes.filter(
        Q(price__gt=5) & ~Q(name="Japans finest")
    ).all()
    assert c3 not in coffees_5_not_japans

    empty_Q_condition = await Coffee.nodes.filter(Q(price=5) | Q()).all()
    assert (
        len(empty_Q_condition) == 1
    ), "undefined Q leading to unexpected number of results"
    assert c1 in empty_Q_condition

    combined_coffees = await Coffee.nodes.filter(
        Q(price=35), Q(name="Latte") | Q(name="Cappuccino")
    ).all()
    assert len(combined_coffees) == 2
    assert c5 in combined_coffees
    assert c6 in combined_coffees
    assert c3 not in combined_coffees

    class QQ:
        pass

    with raises(TypeError):
        wrong_Q = await Coffee.nodes.filter(Q(price=5) | QQ()).all()


def test_qbase():
    test_print_out = str(Q(price=5) | Q(price=10))
    test_repr = repr(Q(price=5) | Q(price=10))
    assert test_print_out == "(OR: ('price', 5), ('price', 10))"
    assert test_repr == "<Q: (OR: ('price', 5), ('price', 10))>"

    assert ("price", 5) in (Q(price=5) | Q(price=10))

    test_hash = set([Q(price_lt=30) | ~Q(price=5), Q(price_lt=30) | ~Q(price=5)])
    assert len(test_hash) == 1


@mark_async_test
async def test_traversal_filter_left_hand_statement():
    nescafe = await Coffee(name="Nescafe2", price=99).save()
    nescafe_gold = await Coffee(name="Nescafe gold", price=11).save()

    tesco = await Supplier(name="Sainsburys", delivery_cost=3).save()
    biedronka = await Supplier(name="Biedronka", delivery_cost=5).save()
    lidl = await Supplier(name="Lidl", delivery_cost=3).save()

    await nescafe.suppliers.connect(tesco)
    await nescafe_gold.suppliers.connect(biedronka)
    await nescafe_gold.suppliers.connect(lidl)

    lidl_supplier = (
        await AsyncNodeSet(Coffee.nodes.filter(price=11).suppliers)
        .filter(delivery_cost=3)
        .all()
    )

    assert lidl in lidl_supplier


@mark_async_test
async def test_fetch_relations():
    arabica = await Species(name="Arabica").save()
    robusta = await Species(name="Robusta").save()
    nescafe = await Coffee(name="Nescafe 1000", price=99).save()
    nescafe_gold = await Coffee(name="Nescafe 1001", price=11).save()

    tesco = await Supplier(name="Sainsburys", delivery_cost=3).save()
    await nescafe.suppliers.connect(tesco)
    await nescafe_gold.suppliers.connect(tesco)
    await nescafe.species.connect(arabica)

    result = (
        await Supplier.nodes.filter(name="Sainsburys")
        .fetch_relations("coffees__species")
        .all()
    )
    assert len(result[0]) == 5
    assert arabica in result[0]
    assert robusta not in result[0]
    assert tesco in result[0]
    assert nescafe in result[0]
    assert nescafe_gold not in result[0]

    result = (
        await Species.nodes.filter(name="Robusta")
        .fetch_relations(Optional("coffees__suppliers"))
        .all()
    )
    assert result[0][0] is None

    if AsyncUtil.is_async_code:
        count = (
            await Supplier.nodes.filter(name="Sainsburys")
            .fetch_relations("coffees__species")
            .get_len()
        )
        assert count == 1

        assert (
            await Supplier.nodes.fetch_relations("coffees__species")
            .filter(name="Sainsburys")
            .check_contains(tesco)
        )
    else:
        count = len(
            Supplier.nodes.filter(name="Sainsburys")
            .fetch_relations("coffees__species")
            .all()
        )
        assert count == 1

        assert tesco in Supplier.nodes.fetch_relations("coffees__species").filter(
            name="Sainsburys"
        )


@mark_async_test
async def test_issue_795():
    jim = await PersonX(name="Jim", age=3).save()  # Create
    jim.age = 4
    await jim.save()  # Update, (with validation)

    germany = await CountryX(code="DE").save()
    await jim.country.connect(germany)
    berlin = await CityX(name="Berlin").save()
    await berlin.country.connect(germany)
    await jim.city.connect(berlin)

    with raises(
        RelationshipClassNotDefined,
        match=r"[\s\S]*Note that when using the fetch_relations method, the relationship type must be defined in the model.*",
    ):
        _ = await PersonX.nodes.fetch_relations("country").all()


@mark_async_test
async def test_in_filter_with_array_property():
    tags = ["smoother", "sweeter", "chocolate", "sugar"]
    no_match = ["organic"]
    arabica = await Species(name="Arabica", tags=tags).save()

    assert arabica in await Species.nodes.filter(
        tags__in=tags
    ), "Species not found by tags given"
    assert arabica in await Species.nodes.filter(
        Q(tags__in=tags)
    ), "Species not found with Q by tags given"
    assert arabica not in await Species.nodes.filter(
        ~Q(tags__in=tags)
    ), "Species found by tags given in negated query"
    assert arabica not in await Species.nodes.filter(
        tags__in=no_match
    ), "Species found by tags with not match tags given"


@mark_async_test
async def test_async_iterator():
    n = 10
    if AsyncUtil.is_async_code:
        for c in await Coffee.nodes:
            await c.delete()

        for i in range(n):
            await Coffee(name=f"xxx_{i}", price=i).save()

        nodes = await Coffee.nodes
        # assert that nodes was created
        assert isinstance(nodes, list)
        assert all(isinstance(i, Coffee) for i in nodes)
        assert len(nodes) == n

        counter = 0
        async for node in Coffee.nodes:
            assert isinstance(node, Coffee)
            counter += 1

        # assert that generator runs loop above
        assert counter == n

        counter = 0
        for node in await Coffee.nodes:
            assert isinstance(node, Coffee)
            counter += 1

        # assert that generator runs loop above
        assert counter == n
