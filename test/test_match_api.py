from datetime import datetime

from pytest import raises

from neomodel import (StructuredNode, StringProperty, IntegerProperty, RelationshipFrom,
                      RelationshipTo, StructuredRel, DateTimeProperty)
from neomodel.match import NodeSet, QueryBuilder
from neomodel.exceptions import MultipleNodesReturned


class SupplierRel(StructuredRel):
    since = DateTimeProperty(default=datetime.now)
    courier = StringProperty()


class Supplier(StructuredNode):
    name = StringProperty()
    delivery_cost = IntegerProperty()
    coffees = RelationshipTo('Coffee', 'COFFEE SUPPLIERS')  # Space to check for escaping


class Coffee(StructuredNode):
    name = StringProperty(unique_index=True)
    price = IntegerProperty()
    suppliers = RelationshipFrom(Supplier, 'COFFEE SUPPLIERS', model=SupplierRel)


def test_filter_exclude_via_labels():
    Coffee(name='Java', price=99).save()

    node_set = NodeSet(Coffee)
    qb = QueryBuilder(node_set).build_ast()

    results = qb._execute()

    assert '(coffee:Coffee)' in qb._ast['match']
    assert 'result_class' in qb._ast
    assert len(results) == 1
    assert isinstance(results[0], Coffee)
    assert results[0].name == 'Java'

    # with filter and exclude
    Coffee(name='Kenco', price=3).save()
    node_set = node_set.filter(price__gt=2).exclude(price__gt=6, name='Java')
    qb = QueryBuilder(node_set).build_ast()

    results = qb._execute()
    assert '(coffee:Coffee)' in qb._ast['match']
    assert 'NOT' in qb._ast['where'][0]
    assert len(results) == 1
    assert results[0].name == 'Kenco'


def test_simple_has_via_label():
    nescafe = Coffee(name='Nescafe', price=99).save()
    tesco = Supplier(name='Tesco', delivery_cost=2).save()
    nescafe.suppliers.connect(tesco)

    ns = NodeSet(Coffee).has(suppliers=True)
    qb = QueryBuilder(ns).build_ast()
    results = qb._execute()
    assert 'COFFEE SUPPLIERS' in qb._ast['where'][0]
    assert len(results) == 1
    assert results[0].name == 'Nescafe'

    Coffee(name='nespresso', price=99).save()
    ns = NodeSet(Coffee).has(suppliers=False)
    qb = QueryBuilder(ns).build_ast()
    results = qb._execute()
    assert len(results) > 0
    assert 'NOT' in qb._ast['where'][0]


def test_get():
    Coffee(name='1', price=3).save()
    assert Coffee.nodes.get(name='1')

    with raises(Coffee.DoesNotExist):
        Coffee.nodes.get(name='2')

    Coffee(name='2', price=3).save()

    with raises(MultipleNodesReturned):
        Coffee.nodes.get(price=3)


def test_simple_traverse_with_filter():
    nescafe = Coffee(name='Nescafe2', price=99).save()
    tesco = Supplier(name='Sainsburys', delivery_cost=2).save()
    nescafe.suppliers.connect(tesco)

    qb = QueryBuilder(NodeSet(source=nescafe).suppliers.match(since__lt=datetime.now()))

    results = qb.build_ast()._execute()

    assert 'lookup' in qb._ast
    assert 'match' in qb._ast
    assert qb._ast['return'] == 'suppliers'
    assert len(results) == 1
    assert results[0].name == 'Sainsburys'


def test_double_traverse():
    nescafe = Coffee(name='Nescafe plus', price=99).save()
    tesco = Supplier(name='Asda', delivery_cost=2).save()
    nescafe.suppliers.connect(tesco)
    tesco.coffees.connect(Coffee(name='Decafe', price=2).save())

    ns = NodeSet(NodeSet(source=nescafe).suppliers.match()).coffees.match()
    qb = QueryBuilder(ns).build_ast()

    results = qb._execute()
    assert len(results) == 1
    assert results[0].name == 'Decafe'


def test_count():
    Coffee(name='Nescafe Gold', price=99).save()
    count = QueryBuilder(NodeSet(source=Coffee)).build_ast()._count()
    assert count > 0


def test_len_and_iter_and_bool():
    iterations = 0

    Coffee(name="Icelands finest").save()

    for c in Coffee.nodes:
        iterations += 1
        c.delete()

    assert iterations > 0

    assert len(Coffee.nodes) == 0


def test_slice():
    for c in Coffee.nodes:
        c.delete()

    Coffee(name="Icelands finest").save()
    Coffee(name="Britains finest").save()
    Coffee(name="Japans finest").save()

    assert len(Coffee.nodes[1:]) == 2
    assert len(Coffee.nodes[:1]) == 1
    assert isinstance(Coffee.nodes[1], Coffee)
    assert isinstance(Coffee.nodes[0], Coffee)
    assert len(Coffee.nodes[1:2]) == 1


def test_issue_208():
    # calls to match persist across queries.

    b = Coffee(name="basics").save()
    l = Supplier(name="lidl").save()
    a = Supplier(name="aldi").save()

    b.suppliers.connect(l, {'courier': 'fedex'})
    b.suppliers.connect(a, {'courier': 'dhl'})

    assert len(b.suppliers.match(courier='fedex'))
    assert len(b.suppliers.match(courier='dhl'))


def test_contains():
    expensive = Coffee(price=1000, name="Pricey").save()
    asda = Coffee(name='Asda', price=1).save()

    assert expensive in Coffee.nodes.filter(price__gt=999)
    assert asda not in Coffee.nodes.filter(price__gt=999)

    # bad value raises
    with raises(ValueError):
        2 in Coffee.nodes

    # unsaved
    with raises(ValueError):
        Coffee() in Coffee.nodes


def test_order_by():
    for c in Coffee.nodes:
        c.delete()

    c1 = Coffee(name="Icelands finest", price=5).save()
    c2 = Coffee(name="Britains finest", price=10).save()
    c3 = Coffee(name="Japans finest", price=35).save()

    assert Coffee.nodes.order_by('price').all()[0].price == 5
    assert Coffee.nodes.order_by('-price').all()[0].price == 35

    ns = Coffee.nodes.order_by('-price')
    qb = QueryBuilder(ns).build_ast()
    assert qb._ast['order_by']
    ns = ns.order_by(None)
    qb = QueryBuilder(ns).build_ast()
    assert not qb._ast['order_by']
    ns = ns.order_by('?')
    qb = QueryBuilder(ns).build_ast()
    assert qb._ast['with'] == 'coffee, rand() as r'
    assert qb._ast['order_by'] == 'r'

    # Test order by on a relationship
    l = Supplier(name="lidl2").save()
    l.coffees.connect(c1)
    l.coffees.connect(c2)
    l.coffees.connect(c3)

    ordered_n = [n for n in l.coffees.order_by('name').all()]
    assert ordered_n[0] == c2
    assert ordered_n[1] == c1
    assert ordered_n[2] == c3


def test_extra_filters():

    for c in Coffee.nodes:
        c.delete()

    c1 = Coffee(name="Icelands finest", price=5).save()
    c2 = Coffee(name="Britains finest", price=10).save()
    c3 = Coffee(name="Japans finest", price=35).save()
    c4 = Coffee(name="US extra-fine", price=None).save()

    coffees_5_10 = Coffee.nodes.filter(price__in=[10, 5]).all()
    assert len(coffees_5_10) == 2, "unexpected number of results"
    assert c1 in coffees_5_10, "doesnt contain 5 price coffee"
    assert c2 in coffees_5_10, "doesnt contain 10 price coffee"

    finest_coffees = Coffee.nodes.filter(name__iendswith=' Finest').all()
    assert len(finest_coffees) == 3, "unexpected number of results"
    assert c1 in finest_coffees, "doesnt contain 1st finest coffee"
    assert c2 in finest_coffees, "doesnt contain 2nd finest coffee"
    assert c3 in finest_coffees, "doesnt contain 3rd finest coffee"

    unpriced_coffees = Coffee.nodes.filter(price__isnull=True).all()
    assert len(unpriced_coffees) == 1, "unexpected number of results"
    assert c4 in unpriced_coffees, "doesnt contain unpriced coffee"
