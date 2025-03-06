import re
from datetime import datetime
from test._async_compat import mark_sync_test

import numpy as np
from pytest import raises, skip, warns

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
    ZeroOrOne,
    db,
)
from neomodel._async_compat.util import Util
from neomodel.exceptions import MultipleNodesReturned, RelationshipClassNotDefined
from neomodel.sync_.match import (
    Collect,
    Last,
    NodeNameResolver,
    NodeSet,
    Optional,
    QueryBuilder,
    RawCypher,
    RelationNameResolver,
    Size,
    Traversal,
)


class SupplierRel(StructuredRel):
    since = DateTimeProperty(default=datetime.now)
    courier = StringProperty()


class Supplier(StructuredNode):
    name = StringProperty()
    delivery_cost = IntegerProperty()
    coffees = RelationshipTo("Coffee", "COFFEE SUPPLIERS", model=SupplierRel)


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


class SoftwareDependency(StructuredNode):
    name = StringProperty(required=True)
    version = StringProperty(required=True)


class HasCourseRel(StructuredRel):
    level = StringProperty()
    start_date = DateTimeProperty()
    end_date = DateTimeProperty()


class Course(StructuredNode):
    name = StringProperty()


class Building(StructuredNode):
    name = StringProperty()


class Student(StructuredNode):
    name = StringProperty()

    parents = RelationshipTo("Student", "HAS_PARENT", model=StructuredRel)
    children = RelationshipFrom("Student", "HAS_PARENT", model=StructuredRel)
    lives_in = RelationshipTo(Building, "LIVES_IN", model=StructuredRel)
    courses = RelationshipTo(Course, "HAS_COURSE", model=HasCourseRel)
    preferred_course = RelationshipTo(
        Course,
        "HAS_PREFERRED_COURSE",
        model=StructuredRel,
        cardinality=ZeroOrOne,
    )


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
    tesco = Supplier(name="Tesco", delivery_cost=2).save()
    nescafe.suppliers.connect(tesco)

    qb = QueryBuilder(NodeSet(source=nescafe).suppliers.match(since__lt=datetime.now()))

    _ast = qb.build_ast()
    results = [node for node in qb._execute()]

    assert qb._ast.lookup
    assert qb._ast.match
    assert qb._ast.return_clause.startswith("suppliers")
    assert len(results) == 1
    assert results[0].name == "Tesco"


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
    assert qb._ast.order_by == ["r"]

    with raises(
        ValueError,
        match=r".*Neo4j internals like id or element_id are not allowed for use in this operation.",
    ):
        Coffee.nodes.order_by("id").all()

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
def test_order_by_rawcypher():
    d1 = SoftwareDependency(name="Package1", version="1.0.0").save()
    d2 = SoftwareDependency(name="Package2", version="1.4.0").save()
    d3 = SoftwareDependency(name="Package3", version="2.5.5").save()

    assert (
        SoftwareDependency.nodes.order_by(
            RawCypher("toInteger(split($n.version, '.')[0]) DESC"),
        ).all()
    )[0] == d3

    with raises(
        ValueError, match=r"RawCypher: Do not include any action that has side effect"
    ):
        SoftwareDependency.nodes.order_by(
            RawCypher("DETACH DELETE $n"),
        )


@mark_sync_test
def test_extra_filters():
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

    with raises(
        ValueError,
        match=r"Cannot filter using OR operator on variables coming from both MATCH and OPTIONAL MATCH statements",
    ):
        Coffee.nodes.fetch_relations(Optional("species")).filter(
            Q(name="Latte") | Q(species__name="Robusta")
        ).all()

    class QQ:
        pass

    with raises(TypeError):
        Coffee.nodes.filter(Q(price=5) | QQ()).all()


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

    tesco = Supplier(name="Tesco", delivery_cost=3).save()
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
def test_filter_with_traversal():
    arabica = Species(name="Arabica").save()
    robusta = Species(name="Robusta").save()
    nescafe = Coffee(name="Nescafe", price=11).save()
    nescafe_gold = Coffee(name="Nescafe Gold", price=99).save()
    tesco = Supplier(name="Tesco", delivery_cost=3).save()
    nescafe.suppliers.connect(tesco)
    nescafe_gold.suppliers.connect(tesco)
    nescafe.species.connect(arabica)
    nescafe_gold.species.connect(robusta)

    results = Coffee.nodes.filter(species__name="Arabica").all()
    assert len(results) == 1
    assert len(results[0]) == 3
    assert results[0][0] == nescafe

    results_multi_hop = Supplier.nodes.filter(coffees__species__name="Arabica").all()
    assert len(results_multi_hop) == 1
    assert results_multi_hop[0][0] == tesco

    no_results = Supplier.nodes.filter(coffees__species__name="Noffee").all()
    assert no_results == []


@mark_sync_test
def test_relation_prop_filtering():
    arabica = Species(name="Arabica").save()
    nescafe = Coffee(name="Nescafe", price=99).save()
    supplier1 = Supplier(name="Supplier 1", delivery_cost=3).save()
    supplier2 = Supplier(name="Supplier 2", delivery_cost=20).save()

    nescafe.suppliers.connect(supplier1, {"since": datetime(2020, 4, 1, 0, 0)})
    nescafe.suppliers.connect(supplier2, {"since": datetime(2010, 4, 1, 0, 0)})
    nescafe.species.connect(arabica)

    results = Supplier.nodes.filter(
        **{"coffees__name": "Nescafe", "coffees|since__gt": datetime(2018, 4, 1, 0, 0)}
    ).all()

    assert len(results) == 1
    assert results[0][0] == supplier1

    # Test it works with mixed argument syntaxes
    results2 = Supplier.nodes.filter(
        name="Supplier 1",
        coffees__name="Nescafe",
        **{"coffees|since__gt": datetime(2018, 4, 1, 0, 0)},
    ).all()

    assert len(results2) == 1
    assert results2[0][0] == supplier1


@mark_sync_test
def test_relation_prop_ordering():
    arabica = Species(name="Arabica").save()
    nescafe = Coffee(name="Nescafe", price=99).save()
    supplier1 = Supplier(name="Supplier 1", delivery_cost=3).save()
    supplier2 = Supplier(name="Supplier 2", delivery_cost=20).save()

    nescafe.suppliers.connect(supplier1, {"since": datetime(2020, 4, 1, 0, 0)})
    nescafe.suppliers.connect(supplier2, {"since": datetime(2010, 4, 1, 0, 0)})
    nescafe.species.connect(arabica)

    results = Supplier.nodes.fetch_relations("coffees").order_by("-coffees|since").all()
    assert len(results) == 2
    assert results[0][0] == supplier1
    assert results[1][0] == supplier2

    results = Supplier.nodes.fetch_relations("coffees").order_by("coffees|since").all()
    assert len(results) == 2
    assert results[0][0] == supplier2
    assert results[1][0] == supplier1


@mark_sync_test
def test_fetch_relations():
    arabica = Species(name="Arabica").save()
    robusta = Species(name="Robusta").save()
    nescafe = Coffee(name="Nescafe", price=99).save()
    nescafe_gold = Coffee(name="Nescafe Gold", price=11).save()

    tesco = Supplier(name="Tesco", delivery_cost=3).save()
    nescafe.suppliers.connect(tesco)
    nescafe_gold.suppliers.connect(tesco)
    nescafe.species.connect(arabica)

    result = (
        Supplier.nodes.filter(name="Tesco").fetch_relations("coffees__species").all()
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
    assert len(result) == 1

    if Util.is_async_code:
        count = (
            Supplier.nodes.filter(name="Tesco")
            .fetch_relations("coffees__species")
            .__len__()
        )
        assert count == 1

        assert (
            Supplier.nodes.fetch_relations("coffees__species")
            .filter(name="Tesco")
            .__contains__(tesco)
        )
    else:
        count = len(
            Supplier.nodes.filter(name="Tesco")
            .fetch_relations("coffees__species")
            .all()
        )
        assert count == 1

        assert tesco in Supplier.nodes.fetch_relations("coffees__species").filter(
            name="Tesco"
        )


@mark_sync_test
def test_traverse_and_order_by():
    arabica = Species(name="Arabica").save()
    robusta = Species(name="Robusta").save()
    nescafe = Coffee(name="Nescafe", price=99).save()
    nescafe_gold = Coffee(name="Nescafe Gold", price=110).save()
    tesco = Supplier(name="Tesco", delivery_cost=3).save()
    nescafe.suppliers.connect(tesco)
    nescafe_gold.suppliers.connect(tesco)
    nescafe.species.connect(arabica)
    nescafe_gold.species.connect(robusta)

    results = Species.nodes.fetch_relations("coffees").order_by("-coffees__price").all()
    assert len(results) == 2
    assert len(results[0]) == 3  # 2 nodes and 1 relation
    assert results[0][0] == robusta
    assert results[1][0] == arabica


@mark_sync_test
def test_annotate_and_collect():
    arabica = Species(name="Arabica").save()
    robusta = Species(name="Robusta").save()
    nescafe = Coffee(name="Nescafe 1002", price=99).save()
    nescafe_gold = Coffee(name="Nescafe 1003", price=11).save()

    tesco = Supplier(name="Tesco", delivery_cost=3).save()
    nescafe.suppliers.connect(tesco)
    nescafe_gold.suppliers.connect(tesco)
    nescafe.species.connect(arabica)
    nescafe_gold.species.connect(robusta)
    nescafe_gold.species.connect(arabica)

    result = (
        Supplier.nodes.traverse_relations(species="coffees__species")
        .annotate(Collect("species"))
        .all()
    )
    assert len(result) == 1
    assert len(result[0][1][0]) == 3  # 3 species must be there (with 2 duplicates)

    result = (
        Supplier.nodes.traverse_relations(species="coffees__species")
        .annotate(Collect("species", distinct=True))
        .all()
    )
    assert len(result[0][1][0]) == 2  # 2 species must be there

    result = (
        Supplier.nodes.traverse_relations(species="coffees__species")
        .annotate(Size(Collect("species", distinct=True)))
        .all()
    )
    assert result[0][1] == 2  # 2 species

    result = (
        Supplier.nodes.traverse_relations(species="coffees__species")
        .annotate(all_species=Collect("species", distinct=True))
        .all()
    )
    assert len(result[0][1][0]) == 2  # 2 species must be there

    result = (
        Supplier.nodes.traverse_relations("coffees__species")
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


@mark_sync_test
def test_resolve_subgraph():
    arabica = Species(name="Arabica").save()
    robusta = Species(name="Robusta").save()
    nescafe = Coffee(name="Nescafe", price=99).save()
    nescafe_gold = Coffee(name="Nescafe Gold", price=11).save()

    tesco = Supplier(name="Tesco", delivery_cost=3).save()
    nescafe.suppliers.connect(tesco)
    nescafe_gold.suppliers.connect(tesco)
    nescafe.species.connect(arabica)
    nescafe_gold.species.connect(robusta)

    with raises(
        RuntimeError,
        match=re.escape(
            "Nothing to resolve. Make sure to include relations in the result using fetch_relations() or filter()."
        ),
    ):
        result = Supplier.nodes.resolve_subgraph()

    with raises(
        NotImplementedError,
        match=re.escape(
            "You cannot use traverse_relations() with resolve_subgraph(), use fetch_relations() instead."
        ),
    ):
        result = Supplier.nodes.traverse_relations(
            "coffees__species"
        ).resolve_subgraph()

    result = Supplier.nodes.fetch_relations("coffees__species").resolve_subgraph()
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


@mark_sync_test
def test_resolve_subgraph_optional():
    arabica = Species(name="Arabica").save()
    nescafe = Coffee(name="Nescafe", price=99).save()
    nescafe_gold = Coffee(name="Nescafe Gold", price=11).save()

    tesco = Supplier(name="Tesco", delivery_cost=3).save()
    nescafe.suppliers.connect(tesco)
    nescafe_gold.suppliers.connect(tesco)
    nescafe.species.connect(arabica)

    result = Supplier.nodes.fetch_relations(
        Optional("coffees__species")
    ).resolve_subgraph()
    assert len(result) == 1

    assert hasattr(result[0], "_relations")
    assert "coffees" in result[0]._relations
    coffees = result[0]._relations["coffees"]
    assert hasattr(coffees, "_relations")
    assert "species" in coffees._relations
    assert coffees._relations["species"] == arabica


@mark_sync_test
def test_subquery():
    arabica = Species(name="Arabica").save()
    nescafe = Coffee(name="Nescafe", price=99).save()
    supplier1 = Supplier(name="Supplier 1", delivery_cost=3).save()
    supplier2 = Supplier(name="Supplier 2", delivery_cost=20).save()

    nescafe.suppliers.connect(supplier1)
    nescafe.suppliers.connect(supplier2)
    nescafe.species.connect(arabica)

    subquery = Coffee.nodes.subquery(
        Coffee.nodes.traverse_relations(suppliers="suppliers")
        .intermediate_transform(
            {"suppliers": {"source": "suppliers"}}, ordering=["suppliers.delivery_cost"]
        )
        .annotate(supps=Last(Collect("suppliers"))),
        ["supps"],
        [NodeNameResolver("self")],
    )
    result = subquery.all()
    assert len(result) == 1
    assert len(result[0]) == 2
    assert result[0][0] == supplier2

    with raises(
        RuntimeError,
        match=re.escape("Variable 'unknown' is not returned by subquery."),
    ):
        result = Coffee.nodes.subquery(
            Coffee.nodes.traverse_relations(suppliers="suppliers").annotate(
                supps=Collect("suppliers")
            ),
            ["unknown"],
        )

    result_string_context = subquery.subquery(
        Coffee.nodes.traverse_relations(supps2="suppliers").annotate(
            supps2=Collect("supps")
        ),
        ["supps2"],
        ["supps"],
    )
    result_string_context = result_string_context.all()
    assert len(result) == 1
    additional_elements = [
        item for item in result_string_context[0] if item not in result[0]
    ]
    assert len(additional_elements) == 1
    assert isinstance(additional_elements[0], list)

    with raises(ValueError, match=r"Wrong variable specified in initial context"):
        result = Coffee.nodes.subquery(
            Coffee.nodes.traverse_relations(suppliers="suppliers").annotate(
                supps=Collect("suppliers")
            ),
            ["supps"],
            [2],
        )


@mark_sync_test
def test_subquery_other_node():
    arabica = Species(name="Arabica").save()
    nescafe = Coffee(name="Nescafe", price=99).save()
    supplier1 = Supplier(name="Supplier 1", delivery_cost=3).save()
    supplier2 = Supplier(name="Supplier 2", delivery_cost=20).save()

    nescafe.suppliers.connect(supplier1)
    nescafe.suppliers.connect(supplier2)
    nescafe.species.connect(arabica)

    result = Coffee.nodes.subquery(
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
    result = result.all()
    assert len(result) == 1
    assert result[0][0] == 20


@mark_sync_test
def test_intermediate_transform():
    arabica = Species(name="Arabica").save()
    nescafe = Coffee(name="Nescafe", price=99).save()
    supplier1 = Supplier(name="Supplier 1", delivery_cost=3).save()
    supplier2 = Supplier(name="Supplier 2", delivery_cost=20).save()

    nescafe.suppliers.connect(supplier1, {"since": datetime(2020, 4, 1, 0, 0)})
    nescafe.suppliers.connect(supplier2, {"since": datetime(2010, 4, 1, 0, 0)})
    nescafe.species.connect(arabica)

    result = (
        Coffee.nodes.fetch_relations("suppliers")
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
        Coffee.nodes.traverse_relations(suppliers="suppliers").intermediate_transform(
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
        Coffee.nodes.traverse_relations(suppliers="suppliers").intermediate_transform(
            {}
        )


@mark_sync_test
def test_mix_functions():
    # Test with a mix of all advanced querying functions

    eiffel_tower = Building(name="Eiffel Tower").save()
    empire_state_building = Building(name="Empire State Building").save()
    miranda = Student(name="Miranda").save()
    miranda.lives_in.connect(empire_state_building)
    jean_pierre = Student(name="Jean-Pierre").save()
    jean_pierre.lives_in.connect(eiffel_tower)
    mireille = Student(name="Mireille").save()
    mimoun_jr = Student(name="Mimoun Jr").save()
    mimoun = Student(name="Mimoun").save()
    mireille.lives_in.connect(eiffel_tower)
    mimoun_jr.lives_in.connect(eiffel_tower)
    mimoun.lives_in.connect(eiffel_tower)
    mimoun.parents.connect(mireille)
    mimoun.children.connect(mimoun_jr)
    math = Course(name="Math").save()
    dessin = Course(name="Dessin").save()
    mimoun.courses.connect(
        math,
        {
            "level": "1.2",
            "start_date": datetime(2020, 6, 2),
            "end_date": datetime(2020, 12, 31),
        },
    )
    mimoun.courses.connect(
        math,
        {
            "level": "1.1",
            "start_date": datetime(2020, 1, 1),
            "end_date": datetime(2020, 6, 1),
        },
    )
    mimoun_jr.courses.connect(
        math,
        {
            "level": "1.1",
            "start_date": datetime(2020, 1, 1),
            "end_date": datetime(2020, 6, 1),
        },
    )

    mimoun_jr.preferred_course.connect(dessin)

    full_nodeset = (
        Student.nodes.filter(name__istartswith="m", lives_in__name="Eiffel Tower")
        .order_by("name")
        .fetch_relations(
            "parents",
            Optional("children__preferred_course"),
        )
        .subquery(
            Student.nodes.fetch_relations("courses")
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

    subgraph = full_nodeset.annotate(
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


def assert_last_query_startswith(mock_func, query) -> bool:
    return mock_func.call_args_list[-1].kwargs["query"].startswith(query)


@mark_sync_test
def test_parallel_runtime(mocker):
    if not db.version_is_higher_than("5.13") or not db.edition_is_enterprise():
        skip("Only supported for Enterprise 5.13 and above.")

    assert db.parallel_runtime_available()

    # Parallel should be applied to custom Cypher query
    with db.parallel_read_transaction:
        # Mock transaction.run to access executed query
        # Assert query starts with CYPHER runtime=parallel
        assert db._parallel_runtime == True
        mock_transaction_run = mocker.patch("neo4j.Transaction.run")
        db.cypher_query("MATCH (n:Coffee) RETURN n")
        assert assert_last_query_startswith(
            mock_transaction_run, "CYPHER runtime=parallel"
        )
    # Test exiting the context sets the parallel_runtime to False
    assert db._parallel_runtime == False

    # Parallel should be applied to neomodel queries
    with db.parallel_read_transaction:
        mock_transaction_run_2 = mocker.patch("neo4j.Transaction.run")
        Coffee.nodes.all()
        assert assert_last_query_startswith(
            mock_transaction_run_2, "CYPHER runtime=parallel"
        )


@mark_sync_test
def test_parallel_runtime_conflict(mocker):
    if db.version_is_higher_than("5.13") and db.edition_is_enterprise():
        skip("Test for unavailable parallel runtime.")

    assert not db.parallel_runtime_available()
    mock_transaction_run = mocker.patch("neo4j.Transaction.run")
    with warns(
        UserWarning,
        match="Parallel runtime is only available in Neo4j Enterprise Edition 5.13",
    ):
        with db.parallel_read_transaction:
            Coffee.nodes.all()
            assert not db._parallel_runtime
            assert not assert_last_query_startswith(
                mock_transaction_run, "CYPHER runtime=parallel"
            )
