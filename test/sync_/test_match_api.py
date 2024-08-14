from datetime import datetime
from test._async_compat import mark_sync_test

from pytest import raises

from neomodel import (
    INCOMING,
    ArrayProperty,
    DateTimeProperty,
    IntegerProperty,
    Q,
    RelationshipFrom,
    RelationshipTo,
    StringProperty,
    StructuredNode,
    StructuredRel,
    UniqueIdProperty,
)
from neomodel._async_compat.util import Util
from neomodel.exceptions import MultipleNodesReturned, RelationshipClassNotDefined
from neomodel.sync_.match import NodeSet, Optional, QueryBuilder, Traversal


class SupplierRel(StructuredRel):
    since = DateTimeProperty(default=datetime.now)
    courier = StringProperty()


class Supplier(StructuredNode):
    name = StringProperty()
    delivery_cost = IntegerProperty()
    coffees = RelationshipTo("Coffee", "COFFEE SUPPLIERS")


class Species(StructuredNode):
    name = StringProperty()
    tags = ArrayProperty(StringProperty(), default=list)
    coffees = RelationshipFrom("Coffee", "COFFEE SPECIES", model=StructuredRel)


class Coffee(StructuredNode):
    name = StringProperty(unique_index=True)
    price = IntegerProperty()
    suppliers = RelationshipFrom(Supplier, "COFFEE SUPPLIERS", model=SupplierRel)
    species = RelationshipTo(Species, "COFFEE SPECIES", model=StructuredRel)
    id_ = IntegerProperty()


class Extension(StructuredNode):
    extension = RelationshipTo("Extension", "extension")


class CountryX(StructuredNode):
    code = StringProperty(unique_index=True, required=True)
    inhabitant = RelationshipFrom("PersonX", "IS_FROM")


class CityX(StructuredNode):
    name = StringProperty(required=True)
    country = RelationshipTo(CountryX, "FROM_COUNTRY")


class PersonX(StructuredNode):
    uid = UniqueIdProperty()
    name = StringProperty(unique_index=True)
    age = IntegerProperty(index=True, default=0)

    # traverse outgoing IS_FROM relations, inflate to Country objects
    country = RelationshipTo(CountryX, "IS_FROM")

    # traverse outgoing LIVES_IN relations, inflate to City objects
    city = RelationshipTo(CityX, "LIVES_IN")


@mark_sync_test
def test_filter_exclude_via_labels():
    Coffee(name="Java", price=99).save()

    node_set = NodeSet(Coffee)
    qb = QueryBuilder(node_set).build_ast()

    results = [node for node in qb._execute()]

    assert "(coffee:Coffee)" in qb._ast.match
    assert qb._ast.result_class
    assert len(results) == 1
    assert isinstance(results[0], Coffee)
    assert results[0].name == "Java"

    # with filter and exclude
    Coffee(name="Kenco", price=3).save()
    node_set = node_set.filter(price__gt=2).exclude(price__gt=6, name="Java")
    qb = QueryBuilder(node_set).build_ast()

    results = [node for node in qb._execute()]
    assert "(coffee:Coffee)" in qb._ast.match
    assert "NOT" in qb._ast.where[0]
    assert len(results) == 1
    assert results[0].name == "Kenco"


@mark_sync_test
def test_simple_has_via_label():
    nescafe = Coffee(name="Nescafe", price=99).save()
    tesco = Supplier(name="Tesco", delivery_cost=2).save()
    nescafe.suppliers.connect(tesco)

    ns = NodeSet(Coffee).has(suppliers=True)
    qb = QueryBuilder(ns).build_ast()
    results = [node for node in qb._execute()]
    assert "COFFEE SUPPLIERS" in qb._ast.where[0]
    assert len(results) == 1
    assert results[0].name == "Nescafe"

    Coffee(name="nespresso", price=99).save()
    ns = NodeSet(Coffee).has(suppliers=False)
    qb = QueryBuilder(ns).build_ast()
    results = [node for node in qb._execute()]
    assert len(results) > 0
    assert "NOT" in qb._ast.where[0]


@mark_sync_test
def test_get():
    Coffee(name="1", price=3).save()
    assert Coffee.nodes.get(name="1")

    with raises(Coffee.DoesNotExist):
        Coffee.nodes.get(name="2")

    Coffee(name="2", price=3).save()

    with raises(MultipleNodesReturned):
        Coffee.nodes.get(price=3)


@mark_sync_test
def test_simple_traverse_with_filter():
    nescafe = Coffee(name="Nescafe2", price=99).save()
    tesco = Supplier(name="Sainsburys", delivery_cost=2).save()
    nescafe.suppliers.connect(tesco)

    qb = QueryBuilder(NodeSet(source=nescafe).suppliers.match(since__lt=datetime.now()))

    _ast = qb.build_ast()
    results = [node for node in qb._execute()]

    assert qb._ast.lookup
    assert qb._ast.match
    assert qb._ast.return_clause.startswith("suppliers")
    assert len(results) == 1
    assert results[0].name == "Sainsburys"


@mark_sync_test
def test_double_traverse():
    nescafe = Coffee(name="Nescafe plus", price=99).save()
    tesco = Supplier(name="Asda", delivery_cost=2).save()
    nescafe.suppliers.connect(tesco)
    tesco.coffees.connect(Coffee(name="Decafe", price=2).save())

    ns = NodeSet(NodeSet(source=nescafe).suppliers.match()).coffees.match()
    qb = QueryBuilder(ns).build_ast()

    results = [node for node in qb._execute()]
    assert len(results) == 2
    names = [n.name for n in results]
    assert "Decafe" in names
    assert "Nescafe plus" in names


@mark_sync_test
def test_count():
    Coffee(name="Nescafe Gold", price=99).save()
    ast = QueryBuilder(NodeSet(source=Coffee)).build_ast()
    count = ast._count()
    assert count > 0

    Coffee(name="Kawa", price=27).save()
    node_set = NodeSet(source=Coffee)
    node_set.skip = 1
    node_set.limit = 1
    ast = QueryBuilder(node_set).build_ast()
    count = ast._count()
    assert count == 1


@mark_sync_test
def test_len_and_iter_and_bool():
    iterations = 0

    Coffee(name="Icelands finest").save()

    for c in Coffee.nodes:
        iterations += 1
        c.delete()

    assert iterations > 0

    assert len(Coffee.nodes) == 0


@mark_sync_test
def test_slice():
    for c in Coffee.nodes:
        c.delete()

    Coffee(name="Icelands finest").save()
    Coffee(name="Britains finest").save()
    Coffee(name="Japans finest").save()

    # Branching tests because async needs extra brackets
    if Util.is_async_code:
        assert len(list((Coffee.nodes)[1:])) == 2
        assert len(list((Coffee.nodes)[:1])) == 1
        assert isinstance((Coffee.nodes)[1], Coffee)
        assert isinstance((Coffee.nodes)[0], Coffee)
        assert len(list((Coffee.nodes)[1:2])) == 1
    else:
        assert len(list(Coffee.nodes[1:])) == 2
        assert len(list(Coffee.nodes[:1])) == 1
        assert isinstance(Coffee.nodes[1], Coffee)
        assert isinstance(Coffee.nodes[0], Coffee)
        assert len(list(Coffee.nodes[1:2])) == 1


@mark_sync_test
def test_issue_208():
    # calls to match persist across queries.

    b = Coffee(name="basics").save()
    l = Supplier(name="lidl").save()
    a = Supplier(name="aldi").save()

    b.suppliers.connect(l, {"courier": "fedex"})
    b.suppliers.connect(a, {"courier": "dhl"})

    assert len(b.suppliers.match(courier="fedex"))
    assert len(b.suppliers.match(courier="dhl"))


@mark_sync_test
def test_issue_589():
    node1 = Extension().save()
    node2 = Extension().save()
    assert node2 not in node1.extension
    node1.extension.connect(node2)
    assert node2 in node1.extension


@mark_sync_test
def test_contains():
    expensive = Coffee(price=1000, name="Pricey").save()
    asda = Coffee(name="Asda", price=1).save()

    assert expensive in Coffee.nodes.filter(price__gt=999)
    assert asda not in Coffee.nodes.filter(price__gt=999)

    # bad value raises
    with raises(ValueError, match=r"Expecting StructuredNode instance"):
        if Util.is_async_code:
            assert Coffee.nodes.__contains__(2)
        else:
            assert 2 in Coffee.nodes

    # unsaved
    with raises(ValueError, match=r"Unsaved node"):
        if Util.is_async_code:
            assert Coffee.nodes.__contains__(Coffee())
        else:
            assert Coffee() in Coffee.nodes


@mark_sync_test
def test_order_by():
    for c in Coffee.nodes:
        c.delete()

    c1 = Coffee(name="Icelands finest", price=5).save()
    c2 = Coffee(name="Britains finest", price=10).save()
    c3 = Coffee(name="Japans finest", price=35).save()

    if Util.is_async_code:
        assert ((Coffee.nodes.order_by("price"))[0]).price == 5
        assert ((Coffee.nodes.order_by("-price"))[0]).price == 35
    else:
        assert (Coffee.nodes.order_by("price")[0]).price == 5
        assert (Coffee.nodes.order_by("-price")[0]).price == 35

    ns = Coffee.nodes.order_by("-price")
    qb = QueryBuilder(ns).build_ast()
    assert qb._ast.order_by
    ns = ns.order_by(None)
    qb = QueryBuilder(ns).build_ast()
    assert not qb._ast.order_by
    ns = ns.order_by("?")
    qb = QueryBuilder(ns).build_ast()
    assert qb._ast.with_clause == "coffee, rand() as r"
    assert qb._ast.order_by == "r"

    with raises(
        ValueError,
        match=r".*Neo4j internals like id or element_id are not allowed for use in this operation.",
    ):
        Coffee.nodes.order_by("id")

    # Test order by on a relationship
    l = Supplier(name="lidl2").save()
    l.coffees.connect(c1)
    l.coffees.connect(c2)
    l.coffees.connect(c3)

    ordered_n = [n for n in l.coffees.order_by("name")]
    assert ordered_n[0] == c2
    assert ordered_n[1] == c1
    assert ordered_n[2] == c3


@mark_sync_test
def test_extra_filters():
    for c in Coffee.nodes:
        c.delete()

    c1 = Coffee(name="Icelands finest", price=5, id_=1).save()
    c2 = Coffee(name="Britains finest", price=10, id_=2).save()
    c3 = Coffee(name="Japans finest", price=35, id_=3).save()
    c4 = Coffee(name="US extra-fine", price=None, id_=4).save()

    coffees_5_10 = Coffee.nodes.filter(price__in=[10, 5])
    assert len(coffees_5_10) == 2, "unexpected number of results"
    assert c1 in coffees_5_10, "doesnt contain 5 price coffee"
    assert c2 in coffees_5_10, "doesnt contain 10 price coffee"

    finest_coffees = Coffee.nodes.filter(name__iendswith=" Finest")
    assert len(finest_coffees) == 3, "unexpected number of results"
    assert c1 in finest_coffees, "doesnt contain 1st finest coffee"
    assert c2 in finest_coffees, "doesnt contain 2nd finest coffee"
    assert c3 in finest_coffees, "doesnt contain 3rd finest coffee"

    unpriced_coffees = Coffee.nodes.filter(price__isnull=True)
    assert len(unpriced_coffees) == 1, "unexpected number of results"
    assert c4 in unpriced_coffees, "doesnt contain unpriced coffee"

    coffees_with_id_gte_3 = Coffee.nodes.filter(id___gte=3)
    assert len(coffees_with_id_gte_3) == 2, "unexpected number of results"
    assert c3 in coffees_with_id_gte_3
    assert c4 in coffees_with_id_gte_3

    with raises(
        ValueError,
        match=r".*Neo4j internals like id or element_id are not allowed for use in this operation.",
    ):
        Coffee.nodes.filter(elementId="4:xxx:111").all()


def test_traversal_definition_keys_are_valid():
    muckefuck = Coffee(name="Mukkefuck", price=1)

    with raises(ValueError):
        Traversal(
            muckefuck,
            "a_name",
            {
                "node_class": Supplier,
                "direction": INCOMING,
                "relationship_type": "KNOWS",
                "model": None,
            },
        )

    Traversal(
        muckefuck,
        "a_name",
        {
            "node_class": Supplier,
            "direction": INCOMING,
            "relation_type": "KNOWS",
            "model": None,
        },
    )


@mark_sync_test
def test_empty_filters():
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

    for c in Coffee.nodes:
        c.delete()

    c1 = Coffee(name="Super", price=5, id_=1).save()
    c2 = Coffee(name="Puper", price=10, id_=2).save()

    empty_filter = Coffee.nodes.filter()

    all_coffees = empty_filter.all()
    assert len(all_coffees) == 2, "unexpected number of results"

    filter_empty_filter = empty_filter.filter(price=5)
    assert len(filter_empty_filter.all()) == 1, "unexpected number of results"
    assert (
        c1 in filter_empty_filter.all()
    ), "doesnt contain c1 in ``filter_empty_filter``"

    filter_q_empty_filter = empty_filter.filter(Q(price=5))
    assert len(filter_empty_filter.all()) == 1, "unexpected number of results"
    assert (
        c1 in filter_empty_filter.all()
    ), "doesnt contain c1 in ``filter_empty_filter``"


@mark_sync_test
def test_q_filters():
    # Test where no children and self.connector != conn ?
    for c in Coffee.nodes:
        c.delete()

    c1 = Coffee(name="Icelands finest", price=5, id_=1).save()
    c2 = Coffee(name="Britains finest", price=10, id_=2).save()
    c3 = Coffee(name="Japans finest", price=35, id_=3).save()
    c4 = Coffee(name="US extra-fine", price=None, id_=4).save()
    c5 = Coffee(name="Latte", price=35, id_=5).save()
    c6 = Coffee(name="Cappuccino", price=35, id_=6).save()

    coffees_5_10 = Coffee.nodes.filter(Q(price=10) | Q(price=5)).all()
    assert len(coffees_5_10) == 2, "unexpected number of results"
    assert c1 in coffees_5_10, "doesnt contain 5 price coffee"
    assert c2 in coffees_5_10, "doesnt contain 10 price coffee"

    coffees_5_6 = (
        Coffee.nodes.filter(Q(name="Latte") | Q(name="Cappuccino"))
        .filter(price=35)
        .all()
    )
    assert len(coffees_5_6) == 2, "unexpected number of results"
    assert c5 in coffees_5_6, "doesnt contain 5 coffee"
    assert c6 in coffees_5_6, "doesnt contain 6 coffee"

    coffees_5_6 = (
        Coffee.nodes.filter(price=35)
        .filter(Q(name="Latte") | Q(name="Cappuccino"))
        .all()
    )
    assert len(coffees_5_6) == 2, "unexpected number of results"
    assert c5 in coffees_5_6, "doesnt contain 5 coffee"
    assert c6 in coffees_5_6, "doesnt contain 6 coffee"

    finest_coffees = Coffee.nodes.filter(name__iendswith=" Finest").all()
    assert len(finest_coffees) == 3, "unexpected number of results"
    assert c1 in finest_coffees, "doesnt contain 1st finest coffee"
    assert c2 in finest_coffees, "doesnt contain 2nd finest coffee"
    assert c3 in finest_coffees, "doesnt contain 3rd finest coffee"

    unpriced_coffees = Coffee.nodes.filter(Q(price__isnull=True)).all()
    assert len(unpriced_coffees) == 1, "unexpected number of results"
    assert c4 in unpriced_coffees, "doesnt contain unpriced coffee"

    coffees_with_id_gte_3 = Coffee.nodes.filter(Q(id___gte=3)).all()
    assert len(coffees_with_id_gte_3) == 4, "unexpected number of results"
    assert c3 in coffees_with_id_gte_3
    assert c4 in coffees_with_id_gte_3
    assert c5 in coffees_with_id_gte_3
    assert c6 in coffees_with_id_gte_3

    coffees_5_not_japans = Coffee.nodes.filter(
        Q(price__gt=5) & ~Q(name="Japans finest")
    ).all()
    assert c3 not in coffees_5_not_japans

    empty_Q_condition = Coffee.nodes.filter(Q(price=5) | Q()).all()
    assert (
        len(empty_Q_condition) == 1
    ), "undefined Q leading to unexpected number of results"
    assert c1 in empty_Q_condition

    combined_coffees = Coffee.nodes.filter(
        Q(price=35), Q(name="Latte") | Q(name="Cappuccino")
    ).all()
    assert len(combined_coffees) == 2
    assert c5 in combined_coffees
    assert c6 in combined_coffees
    assert c3 not in combined_coffees

    class QQ:
        pass

    with raises(TypeError):
        wrong_Q = Coffee.nodes.filter(Q(price=5) | QQ()).all()


def test_qbase():
    test_print_out = str(Q(price=5) | Q(price=10))
    test_repr = repr(Q(price=5) | Q(price=10))
    assert test_print_out == "(OR: ('price', 5), ('price', 10))"
    assert test_repr == "<Q: (OR: ('price', 5), ('price', 10))>"

    assert ("price", 5) in (Q(price=5) | Q(price=10))

    test_hash = set([Q(price_lt=30) | ~Q(price=5), Q(price_lt=30) | ~Q(price=5)])
    assert len(test_hash) == 1


@mark_sync_test
def test_traversal_filter_left_hand_statement():
    nescafe = Coffee(name="Nescafe2", price=99).save()
    nescafe_gold = Coffee(name="Nescafe gold", price=11).save()

    tesco = Supplier(name="Sainsburys", delivery_cost=3).save()
    biedronka = Supplier(name="Biedronka", delivery_cost=5).save()
    lidl = Supplier(name="Lidl", delivery_cost=3).save()

    nescafe.suppliers.connect(tesco)
    nescafe_gold.suppliers.connect(biedronka)
    nescafe_gold.suppliers.connect(lidl)

    lidl_supplier = (
        NodeSet(Coffee.nodes.filter(price=11).suppliers).filter(delivery_cost=3).all()
    )

    assert lidl in lidl_supplier


@mark_sync_test
def test_fetch_relations():
    arabica = Species(name="Arabica").save()
    robusta = Species(name="Robusta").save()
    nescafe = Coffee(name="Nescafe 1000", price=99).save()
    nescafe_gold = Coffee(name="Nescafe 1001", price=11).save()

    tesco = Supplier(name="Sainsburys", delivery_cost=3).save()
    nescafe.suppliers.connect(tesco)
    nescafe_gold.suppliers.connect(tesco)
    nescafe.species.connect(arabica)

    result = (
        Supplier.nodes.filter(name="Sainsburys")
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
        Species.nodes.filter(name="Robusta")
        .fetch_relations(Optional("coffees__suppliers"))
        .all()
    )
    assert result[0][0] is None

    if Util.is_async_code:
        count = (
            Supplier.nodes.filter(name="Sainsburys")
            .fetch_relations("coffees__species")
            .__len__()
        )
        assert count == 1

        assert (
            Supplier.nodes.fetch_relations("coffees__species")
            .filter(name="Sainsburys")
            .__contains__(tesco)
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


@mark_sync_test
def test_issue_795():
    jim = PersonX(name="Jim", age=3).save()  # Create
    jim.age = 4
    jim.save()  # Update, (with validation)

    germany = CountryX(code="DE").save()
    jim.country.connect(germany)
    berlin = CityX(name="Berlin").save()
    berlin.country.connect(germany)
    jim.city.connect(berlin)

    with raises(
        RelationshipClassNotDefined,
        match=r"[\s\S]*Note that when using the fetch_relations method, the relationship type must be defined in the model.*",
    ):
        _ = PersonX.nodes.fetch_relations("country").all()


@mark_sync_test
def test_in_filter_with_array_property():
    tags = ["smoother", "sweeter", "chocolate", "sugar"]
    no_match = ["organic"]
    arabica = Species(name="Arabica", tags=tags).save()

    assert arabica in Species.nodes.filter(
        tags__in=tags
    ), "Species not found by tags given"
    assert arabica in Species.nodes.filter(
        Q(tags__in=tags)
    ), "Species not found with Q by tags given"
    assert arabica not in Species.nodes.filter(
        ~Q(tags__in=tags)
    ), "Species found by tags given in negated query"
    assert arabica not in Species.nodes.filter(
        tags__in=no_match
    ), "Species found by tags with not match tags given"


@mark_sync_test
def test_async_iterator():
    n = 10
    if Util.is_async_code:
        for c in Coffee.nodes:
            c.delete()

        for i in range(n):
            Coffee(name=f"xxx_{i}", price=i).save()

        nodes = Coffee.nodes
        # assert that nodes was created
        assert isinstance(nodes, list)
        assert all(isinstance(i, Coffee) for i in nodes)
        assert len(nodes) == n

        counter = 0
        for node in Coffee.nodes:
            assert isinstance(node, Coffee)
            counter += 1

        # assert that generator runs loop above
        assert counter == n

        counter = 0
        for node in Coffee.nodes:
            assert isinstance(node, Coffee)
            counter += 1

        # assert that generator runs loop above
        assert counter == n
