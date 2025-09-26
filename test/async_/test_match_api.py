import re
from datetime import datetime
from test._async_compat import mark_async_test

from pytest import raises, skip, warns

from neomodel import (
    ArrayProperty,
    AsyncRelationshipFrom,
    AsyncRelationshipTo,
    AsyncStructuredNode,
    AsyncStructuredRel,
    AsyncZeroOrOne,
    DateTimeProperty,
    IntegerProperty,
    Q,
    StringProperty,
    UniqueIdProperty,
    adb,
)
from neomodel._async_compat.util import AsyncUtil
from neomodel.async_.match import (
    AsyncNodeSet,
    AsyncQueryBuilder,
    AsyncTraversal,
    Collect,
    Last,
    NodeNameResolver,
    Optional,
    Path,
    RawCypher,
    RelationNameResolver,
    Size,
)
from neomodel.exceptions import MultipleNodesReturned, RelationshipClassNotDefined
from neomodel.util import RelationshipDirection


class SupplierRel(AsyncStructuredRel):
    since = DateTimeProperty(default=datetime.now)
    courier = StringProperty()


class Supplier(AsyncStructuredNode):
    name = StringProperty()
    delivery_cost = IntegerProperty()
    coffees = AsyncRelationshipTo("Coffee", "COFFEE SUPPLIERS", model=SupplierRel)


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


class SoftwareDependency(AsyncStructuredNode):
    name = StringProperty(required=True)
    version = StringProperty(required=True)


class HasCourseRel(AsyncStructuredRel):
    level = StringProperty()
    start_date = DateTimeProperty()
    end_date = DateTimeProperty()


class Course(AsyncStructuredNode):
    name = StringProperty()


class Building(AsyncStructuredNode):
    name = StringProperty()


class Student(AsyncStructuredNode):
    name = StringProperty()

    parents = AsyncRelationshipTo("Student", "HAS_PARENT", model=AsyncStructuredRel)
    children = AsyncRelationshipFrom("Student", "HAS_PARENT", model=AsyncStructuredRel)
    lives_in = AsyncRelationshipTo(Building, "LIVES_IN", model=AsyncStructuredRel)
    courses = AsyncRelationshipTo(Course, "HAS_COURSE", model=HasCourseRel)
    preferred_course = AsyncRelationshipTo(
        Course,
        "HAS_PREFERRED_COURSE",
        model=AsyncStructuredRel,
        cardinality=AsyncZeroOrOne,
    )


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
    tesco = await Supplier(name="Tesco", delivery_cost=2).save()
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
    assert results[0].name == "Tesco"


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
    assert qb._ast.order_by == ["r"]

    with raises(
        ValueError,
        match=r".*Neo4j internals like id or element_id are not allowed for use in this operation.",
    ):
        await Coffee.nodes.order_by("id").all()

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
async def test_order_by_rawcypher():
    d1 = await SoftwareDependency(name="Package1", version="1.0.0").save()
    d2 = await SoftwareDependency(name="Package2", version="1.4.0").save()
    d3 = await SoftwareDependency(name="Package3", version="2.5.5").save()

    assert (
        await SoftwareDependency.nodes.order_by(
            RawCypher("toInteger(split($n.version, '.')[0]) DESC"),
        ).all()
    )[0] == d3

    with raises(
        ValueError, match=r"RawCypher: Do not include any action that has side effect"
    ):
        SoftwareDependency.nodes.order_by(
            RawCypher("DETACH DELETE $n"),
        )


@mark_async_test
async def test_extra_filters():
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
                "direction": RelationshipDirection.INCOMING,
                "relationship_type": "KNOWS",
                "model": None,
            },
        )

    AsyncTraversal(
        muckefuck,
        "a_name",
        {
            "node_class": Supplier,
            "direction": RelationshipDirection.INCOMING,
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

    robusta = await Species(name="Robusta").save()
    await c4.species.connect(robusta)
    latte_or_robusta_coffee = (
        await Coffee.nodes.traverse(Path(value="species", optional=True))
        .filter(Q(name="Latte") | Q(species__name="Robusta"))
        .all()
    )
    assert len(latte_or_robusta_coffee) == 2

    arabica = await Species(name="Arabica").save()
    await c1.species.connect(arabica)
    robusta_coffee = (
        await Coffee.nodes.traverse(Path(value="species", optional=True))
        .filter(species__name="Robusta")
        .all()
    )
    # Since the filter is applied on the OPTIONAL MATCH
    # The results will contain all the coffee nodes
    # But only the one connected to the species Robusta will have the species returned
    # Everything else will be None
    assert len(robusta_coffee) == 6
    coffee_with_species = [n[0] for n in robusta_coffee if n[1] is not None]
    assert len(coffee_with_species) == 1
    assert coffee_with_species[0] == c4

    class QQ:
        pass

    with raises(TypeError):
        await Coffee.nodes.filter(Q(price=5) | QQ()).all()


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

    tesco = await Supplier(name="Tesco", delivery_cost=3).save()
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
async def test_filter_with_traversal():
    arabica = await Species(name="Arabica").save()
    robusta = await Species(name="Robusta").save()
    nescafe = await Coffee(name="Nescafe", price=11).save()
    nescafe_gold = await Coffee(name="Nescafe Gold", price=99).save()
    tesco = await Supplier(name="Tesco", delivery_cost=3).save()
    await nescafe.suppliers.connect(tesco)
    await nescafe_gold.suppliers.connect(tesco)
    await nescafe.species.connect(arabica)
    await nescafe_gold.species.connect(robusta)

    results = await Coffee.nodes.filter(species__name="Arabica").all()
    assert len(results) == 1
    assert len(results[0]) == 3
    assert results[0][0] == nescafe

    results_multi_hop = await Supplier.nodes.filter(
        coffees__species__name="Arabica"
    ).all()
    assert len(results_multi_hop) == 1
    assert results_multi_hop[0][0] == tesco

    no_results = await Supplier.nodes.filter(coffees__species__name="Noffee").all()
    assert no_results == []


@mark_async_test
async def test_relation_prop_filtering():
    arabica = await Species(name="Arabica").save()
    nescafe = await Coffee(name="Nescafe", price=99).save()
    supplier1 = await Supplier(name="Supplier 1", delivery_cost=3).save()
    supplier2 = await Supplier(name="Supplier 2", delivery_cost=20).save()

    await nescafe.suppliers.connect(supplier1, {"since": datetime(2020, 4, 1, 0, 0)})
    await nescafe.suppliers.connect(supplier2, {"since": datetime(2010, 4, 1, 0, 0)})
    await nescafe.species.connect(arabica)

    result = await Coffee.nodes.filter(
        **{"suppliers|since__gt": datetime(2010, 4, 1, 0, 0)}
    ).all()
    assert len(result) == 1

    results = await Supplier.nodes.filter(
        **{"coffees__name": "Nescafe", "coffees|since__gt": datetime(2018, 4, 1, 0, 0)}
    ).all()

    assert len(results) == 1
    assert results[0][0] == supplier1

    # Test it works with mixed argument syntaxes
    results2 = await Supplier.nodes.filter(
        name="Supplier 1",
        coffees__name="Nescafe",
        **{"coffees|since__gt": datetime(2018, 4, 1, 0, 0)},
    ).all()

    assert len(results2) == 1
    assert results2[0][0] == supplier1


@mark_async_test
async def test_relation_prop_ordering():
    arabica = await Species(name="Arabica").save()
    nescafe = await Coffee(name="Nescafe", price=99).save()
    supplier1 = await Supplier(name="Supplier 1", delivery_cost=3).save()
    supplier2 = await Supplier(name="Supplier 2", delivery_cost=20).save()

    await nescafe.suppliers.connect(supplier1, {"since": datetime(2020, 4, 1, 0, 0)})
    await nescafe.suppliers.connect(supplier2, {"since": datetime(2010, 4, 1, 0, 0)})
    await nescafe.species.connect(arabica)

    results = await Supplier.nodes.traverse("coffees").order_by("-coffees|since").all()
    assert len(results) == 2
    assert results[0][0] == supplier1
    assert results[1][0] == supplier2

    results = await Supplier.nodes.traverse("coffees").order_by("coffees|since").all()
    assert len(results) == 2
    assert results[0][0] == supplier2
    assert results[1][0] == supplier1


@mark_async_test
async def test_traverse():
    arabica = await Species(name="Arabica").save()
    robusta = await Species(name="Robusta").save()
    nescafe = await Coffee(name="Nescafe", price=99).save()
    nescafe_gold = await Coffee(name="Nescafe Gold", price=11).save()

    tesco = await Supplier(name="Tesco", delivery_cost=3).save()
    await nescafe.suppliers.connect(tesco)
    await nescafe_gold.suppliers.connect(tesco)
    await nescafe.species.connect(arabica)

    result = (
        await Supplier.nodes.filter(name="Tesco")
        .traverse(Path(value="coffees__species", include_rels_in_return=False))
        .all()
    )
    assert len(result[0]) == 3
    assert arabica in result[0]
    assert robusta not in result[0]
    assert tesco in result[0]
    assert nescafe in result[0]
    assert nescafe_gold not in result[0]

    result = (
        await Species.nodes.filter(name="Robusta")
        .traverse(Path(value="coffees__suppliers", optional=True))
        .all()
    )
    assert len(result) == 1

    if AsyncUtil.is_async_code:
        count = (
            await Supplier.nodes.filter(name="Tesco")
            .traverse("coffees__species")
            .get_len()
        )
        assert count == 1

        assert (
            await Supplier.nodes.traverse("coffees__species")
            .filter(name="Tesco")
            .check_contains(tesco)
        )
    else:
        count = len(
            Supplier.nodes.filter(name="Tesco").traverse("coffees__species").all()
        )
        assert count == 1

        assert tesco in Supplier.nodes.traverse("coffees__species").filter(name="Tesco")


@mark_async_test
async def test_traverse_and_order_by():
    arabica = await Species(name="Arabica").save()
    robusta = await Species(name="Robusta").save()
    nescafe = await Coffee(name="Nescafe", price=99).save()
    nescafe_gold = await Coffee(name="Nescafe Gold", price=110).save()
    tesco = await Supplier(name="Tesco", delivery_cost=3).save()
    await nescafe.suppliers.connect(tesco)
    await nescafe_gold.suppliers.connect(tesco)
    await nescafe.species.connect(arabica)
    await nescafe_gold.species.connect(robusta)

    results = await Species.nodes.traverse("coffees").order_by("-coffees__price").all()
    assert len(results) == 2
    assert len(results[0]) == 3  # 2 nodes and 1 relation
    assert results[0][0] == robusta
    assert results[1][0] == arabica


@mark_async_test
async def test_annotate_and_collect():
    arabica = await Species(name="Arabica").save()
    robusta = await Species(name="Robusta").save()
    nescafe = await Coffee(name="Nescafe 1002", price=99).save()
    nescafe_gold = await Coffee(name="Nescafe 1003", price=11).save()

    tesco = await Supplier(name="Tesco", delivery_cost=3).save()
    await nescafe.suppliers.connect(tesco)
    await nescafe_gold.suppliers.connect(tesco)
    await nescafe.species.connect(arabica)
    await nescafe_gold.species.connect(robusta)
    await nescafe_gold.species.connect(arabica)

    result = (
        await Supplier.nodes.traverse(
            species=Path(
                value="coffees__species",
                include_rels_in_return=False,
                include_nodes_in_return=False,
            )
        )
        .annotate(Collect("species"))
        .all()
    )
    assert len(result) == 1
    assert len(result[0][1][0]) == 3  # 3 species must be there (with 2 duplicates)

    result = (
        await Supplier.nodes.traverse(
            species=Path(
                value="coffees__species",
                include_rels_in_return=False,
                include_nodes_in_return=False,
            )
        )
        .annotate(Collect("species", distinct=True))
        .all()
    )
    assert len(result[0][1][0]) == 2  # 2 species must be there

    result = (
        await Supplier.nodes.traverse(
            species=Path(
                value="coffees__species",
                include_rels_in_return=False,
                include_nodes_in_return=False,
            )
        )
        .annotate(Size(Collect("species", distinct=True)))
        .all()
    )
    assert result[0][1] == 2  # 2 species

    result = (
        await Supplier.nodes.traverse(
            species=Path(
                value="coffees__species",
                include_rels_in_return=False,
                include_nodes_in_return=False,
            )
        )
        .annotate(all_species=Collect("species", distinct=True))
        .all()
    )
    assert len(result[0][1][0]) == 2  # 2 species must be there

    result = (
        await Supplier.nodes.traverse(
            species=Path(
                value="coffees__species",
                include_rels_in_return=False,
                include_nodes_in_return=False,
            )
        )
        .annotate(
            all_species=Collect(NodeNameResolver("coffees__species"), distinct=True),
            all_species_rels=Collect(
                RelationNameResolver("coffees__species"), distinct=True
            ),
        )
        .all()
    )
    assert len(result[0][1][0]) == 2  # 2 species must be there
    assert len(result[0][2][0]) == 3  # 3 species relations must be there


@mark_async_test
async def test_resolve_subgraph():
    arabica = await Species(name="Arabica").save()
    robusta = await Species(name="Robusta").save()
    nescafe = await Coffee(name="Nescafe", price=99).save()
    nescafe_gold = await Coffee(name="Nescafe Gold", price=11).save()

    tesco = await Supplier(name="Tesco", delivery_cost=3).save()
    await nescafe.suppliers.connect(tesco)
    await nescafe_gold.suppliers.connect(tesco)
    await nescafe.species.connect(arabica)
    await nescafe_gold.species.connect(robusta)

    with raises(
        RuntimeError,
        match=re.escape(
            "Nothing to resolve. Make sure to include relations in the result using traverse() or filter()."
        ),
    ):
        result = await Supplier.nodes.resolve_subgraph()

    result = await Supplier.nodes.traverse("coffees__species").resolve_subgraph()
    assert len(result) == 2

    assert hasattr(result[0], "_relations")
    assert "coffees" in result[0]._relations
    coffees = result[0]._relations["coffees"]
    assert hasattr(coffees, "_relations")
    assert "species" in coffees._relations

    assert hasattr(result[1], "_relations")
    assert "coffees" in result[1]._relations
    coffees = result[1]._relations["coffees"]
    assert hasattr(coffees, "_relations")
    assert "species" in coffees._relations


@mark_async_test
async def test_resolve_subgraph_optional():
    arabica = await Species(name="Arabica").save()
    nescafe = await Coffee(name="Nescafe", price=99).save()
    nescafe_gold = await Coffee(name="Nescafe Gold", price=11).save()

    tesco = await Supplier(name="Tesco", delivery_cost=3).save()
    await nescafe.suppliers.connect(tesco)
    await nescafe_gold.suppliers.connect(tesco)
    await nescafe.species.connect(arabica)

    result = await Supplier.nodes.traverse(
        Path(value="coffees__species", optional=True)
    ).resolve_subgraph()
    assert len(result) == 1

    assert hasattr(result[0], "_relations")
    assert "coffees" in result[0]._relations
    coffees = result[0]._relations["coffees"]
    assert hasattr(coffees, "_relations")
    assert "species" in coffees._relations
    assert coffees._relations["species"] == arabica


@mark_async_test
async def test_subquery():
    arabica = await Species(name="Arabica").save()
    nescafe = await Coffee(name="Nescafe", price=99).save()
    supplier1 = await Supplier(name="Supplier 1", delivery_cost=3).save()
    supplier2 = await Supplier(name="Supplier 2", delivery_cost=20).save()

    await nescafe.suppliers.connect(supplier1)
    await nescafe.suppliers.connect(supplier2)
    await nescafe.species.connect(arabica)

    subquery = await Coffee.nodes.subquery(
        Coffee.nodes.traverse(suppliers="suppliers")
        .intermediate_transform(
            {"suppliers": {"source": "suppliers"}}, ordering=["suppliers.delivery_cost"]
        )
        .annotate(supps=Last(Collect("suppliers"))),
        ["supps"],
        [NodeNameResolver("self")],
    )
    result = await subquery.all()
    assert len(result) == 1
    assert len(result[0]) == 2
    assert result[0][0] == supplier2

    with raises(
        RuntimeError,
        match=re.escape("Variable 'unknown' is not returned by subquery."),
    ):
        result = await Coffee.nodes.subquery(
            Coffee.nodes.traverse(suppliers="suppliers").annotate(
                supps=Collect("suppliers")
            ),
            ["unknown"],
        )

    result_string_context = await subquery.subquery(
        Coffee.nodes.traverse(supps2="suppliers").annotate(supps2=Collect("supps")),
        ["supps2"],
        ["supps"],
    )
    result_string_context = await result_string_context.all()
    assert len(result) == 1
    additional_elements = [
        item for item in result_string_context[0] if item not in result[0]
    ]
    assert len(additional_elements) == 1
    assert isinstance(additional_elements[0], list)

    with raises(ValueError, match=r"Wrong variable specified in initial context"):
        result = await Coffee.nodes.subquery(
            Coffee.nodes.traverse(suppliers="suppliers").annotate(
                supps=Collect("suppliers")
            ),
            ["supps"],
            [2],
        )


@mark_async_test
async def test_subquery_other_node():
    arabica = await Species(name="Arabica").save()
    nescafe = await Coffee(name="Nescafe", price=99).save()
    supplier1 = await Supplier(name="Supplier 1", delivery_cost=3).save()
    supplier2 = await Supplier(name="Supplier 2", delivery_cost=20).save()

    await nescafe.suppliers.connect(supplier1)
    await nescafe.suppliers.connect(supplier2)
    await nescafe.species.connect(arabica)

    result = await Coffee.nodes.subquery(
        Supplier.nodes.filter(name="Supplier 2").intermediate_transform(
            {
                "cost": {
                    "source": "supplier",
                    "source_prop": "delivery_cost",
                    "include_in_return": True,
                }
            }
        ),
        ["cost"],
    )
    result = await result.all()
    assert len(result) == 1
    assert result[0][0] == 20


@mark_async_test
async def test_intermediate_transform():
    arabica = await Species(name="Arabica").save()
    nescafe = await Coffee(name="Nescafe", price=99).save()
    supplier1 = await Supplier(name="Supplier 1", delivery_cost=3).save()
    supplier2 = await Supplier(name="Supplier 2", delivery_cost=20).save()

    await nescafe.suppliers.connect(supplier1, {"since": datetime(2020, 4, 1, 0, 0)})
    await nescafe.suppliers.connect(supplier2, {"since": datetime(2010, 4, 1, 0, 0)})
    await nescafe.species.connect(arabica)

    result = (
        await Coffee.nodes.traverse("suppliers")
        .intermediate_transform(
            {
                "coffee": {"source": "coffee", "include_in_return": True},
                "suppliers": {"source": NodeNameResolver("suppliers")},
                "r": {"source": RelationNameResolver("suppliers")},
                "cost": {
                    "source": NodeNameResolver("suppliers"),
                    "source_prop": "delivery_cost",
                },
            },
            distinct=True,
            ordering=["-r.since"],
        )
        .annotate(oldest_supplier=Last(Collect("suppliers")))
        .all()
    )

    assert len(result) == 1
    assert result[0][0] == nescafe
    assert result[0][1] == supplier2

    with raises(
        ValueError,
        match=re.escape(
            r"Wrong source type specified for variable 'test', should be a string or an instance of NodeNameResolver or RelationNameResolver"
        ),
    ):
        Coffee.nodes.traverse(suppliers="suppliers").intermediate_transform(
            {
                "test": {"source": Collect("suppliers")},
            }
        )
    with raises(
        ValueError,
        match=re.escape(
            r"You must provide one variable at least when calling intermediate_transform()"
        ),
    ):
        Coffee.nodes.traverse(suppliers="suppliers").intermediate_transform({})


@mark_async_test
async def test_mix_functions():
    # Test with a mix of all advanced querying functions

    eiffel_tower = await Building(name="Eiffel Tower").save()
    empire_state_building = await Building(name="Empire State Building").save()
    miranda = await Student(name="Miranda").save()
    await miranda.lives_in.connect(empire_state_building)
    jean_pierre = await Student(name="Jean-Pierre").save()
    await jean_pierre.lives_in.connect(eiffel_tower)
    mireille = await Student(name="Mireille").save()
    mimoun_jr = await Student(name="Mimoun Jr").save()
    mimoun = await Student(name="Mimoun").save()
    await mireille.lives_in.connect(eiffel_tower)
    await mimoun_jr.lives_in.connect(eiffel_tower)
    await mimoun.lives_in.connect(eiffel_tower)
    await mimoun.parents.connect(mireille)
    await mimoun.children.connect(mimoun_jr)
    math = await Course(name="Math").save()
    dessin = await Course(name="Dessin").save()
    await mimoun.courses.connect(
        math,
        {
            "level": "1.2",
            "start_date": datetime(2020, 6, 2),
            "end_date": datetime(2020, 12, 31),
        },
    )
    await mimoun.courses.connect(
        math,
        {
            "level": "1.1",
            "start_date": datetime(2020, 1, 1),
            "end_date": datetime(2020, 6, 1),
        },
    )
    await mimoun_jr.courses.connect(
        math,
        {
            "level": "1.1",
            "start_date": datetime(2020, 1, 1),
            "end_date": datetime(2020, 6, 1),
        },
    )

    await mimoun_jr.preferred_course.connect(dessin)

    full_nodeset = (
        await Student.nodes.filter(name__istartswith="m", lives_in__name="Eiffel Tower")
        .order_by("name")
        .traverse(
            "parents",
            Path(value="children__preferred_course", optional=True),
        )
        .subquery(
            Student.nodes.traverse("courses")
            .intermediate_transform(
                {"rel": {"source": RelationNameResolver("courses")}},
                ordering=[
                    RawCypher("toInteger(split(rel.level, '.')[0])"),
                    RawCypher("toInteger(split(rel.level, '.')[1])"),
                    "rel.end_date",
                    "rel.start_date",
                ],
            )
            .annotate(
                latest_course=Last(Collect("rel")),
            ),
            ["latest_course"],
        )
    )

    subgraph = await full_nodeset.annotate(
        children=Collect(NodeNameResolver("children"), distinct=True),
        children_preferred_course=Collect(
            NodeNameResolver("children__preferred_course"), distinct=True
        ),
    ).resolve_subgraph()

    assert len(subgraph) == 2
    assert subgraph[0] == mimoun
    assert subgraph[1] == mimoun_jr
    mimoun_returned_rels = subgraph[0]._relations
    assert mimoun_returned_rels["children"] == mimoun_jr
    assert mimoun_returned_rels["children"]._relations["preferred_course"] == dessin
    assert mimoun_returned_rels["parents"] == mireille
    assert mimoun_returned_rels["latest_course_relationship"].level == "1.2"


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
        match=r"[\s\S]*Note that when using the traverse method, the relationship type must be defined in the model.*",
    ):
        _ = await PersonX.nodes.traverse("country").all()


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
async def test_unique_variables():
    arabica = await Species(name="Arabica").save()
    nescafe = await Coffee(name="Nescafe", price=99).save()
    gold3000 = await Coffee(name="Gold 3000", price=11).save()
    supplier1 = await Supplier(name="Supplier 1", delivery_cost=3).save()
    supplier2 = await Supplier(name="Supplier 2", delivery_cost=20).save()
    supplier3 = await Supplier(name="Supplier 3", delivery_cost=20).save()

    await nescafe.suppliers.connect(supplier1, {"since": datetime(2020, 4, 1, 0, 0)})
    await nescafe.suppliers.connect(supplier2, {"since": datetime(2010, 4, 1, 0, 0)})
    await nescafe.species.connect(arabica)
    await gold3000.suppliers.connect(supplier1, {"since": datetime(2020, 4, 1, 0, 0)})
    await gold3000.species.connect(arabica)

    nodeset = Supplier.nodes.traverse("coffees", "coffees__species").filter(
        coffees__name="Nescafe"
    )
    ast = await nodeset.query_cls(nodeset).build_ast()
    query = ast.build_query()
    assert "coffee_coffees1" in query
    assert "coffee_coffees2" in query
    results = await nodeset.all()
    # This will be 3 because 2 suppliers for Nescafe and 1 for Gold 3000
    # Gold 3000 is traversed because coffees__species redefines the coffees traversal
    assert len(results) == 3

    nodeset = (
        Supplier.nodes.traverse("coffees", "coffees__species")
        .filter(coffees__name="Nescafe")
        .unique_variables("coffees")
    )
    ast = await nodeset.query_cls(nodeset).build_ast()
    query = ast.build_query()
    assert "coffee_coffees" in query
    assert "coffee_coffees1" not in query
    assert "coffee_coffees2" not in query
    results = await nodeset.all()
    # This will 2 because Gold 3000 is excluded this time
    # As coffees will be reused in coffees__species
    assert len(results) == 2


@mark_async_test
async def test_async_iterator():
    n = 10
    if AsyncUtil.is_async_code:
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


def assert_last_query_startswith(mock_func, query) -> bool:
    return mock_func.call_args_list[-1].kwargs["query"].startswith(query)


@mark_async_test
async def test_parallel_runtime(mocker):
    if (
        not await adb.version_is_higher_than("5.13")
        or not await adb.edition_is_enterprise()
    ):
        skip("Only supported for Enterprise 5.13 and above.")

    assert await adb.parallel_runtime_available()

    # Parallel should be applied to custom Cypher query
    async with adb.parallel_read_transaction:
        # Mock transaction.run to access executed query
        # Assert query starts with CYPHER runtime=parallel
        assert adb._parallel_runtime == True
        mock_transaction_run = mocker.patch("neo4j.AsyncTransaction.run")
        await adb.cypher_query("MATCH (n:Coffee) RETURN n")
        assert assert_last_query_startswith(
            mock_transaction_run, "CYPHER runtime=parallel"
        )
    # Test exiting the context sets the parallel_runtime to False
    assert adb._parallel_runtime == False

    # Parallel should be applied to neomodel queries
    async with adb.parallel_read_transaction:
        mock_transaction_run_2 = mocker.patch("neo4j.AsyncTransaction.run")
        await Coffee.nodes.all()
        assert assert_last_query_startswith(
            mock_transaction_run_2, "CYPHER runtime=parallel"
        )


@mark_async_test
async def test_parallel_runtime_conflict(mocker):
    if await adb.version_is_higher_than("5.13") and await adb.edition_is_enterprise():
        skip("Test for unavailable parallel runtime.")

    assert not await adb.parallel_runtime_available()
    mock_transaction_run = mocker.patch("neo4j.AsyncTransaction.run")
    with warns(
        UserWarning,
        match="Parallel runtime is only available in Neo4j Enterprise Edition 5.13",
    ):
        async with adb.parallel_read_transaction:
            await Coffee.nodes.all()
            assert not adb._parallel_runtime
            assert not assert_last_query_startswith(
                mock_transaction_run, "CYPHER runtime=parallel"
            )
