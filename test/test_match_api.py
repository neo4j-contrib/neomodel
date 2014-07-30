from neomodel import (StructuredNode, StringProperty, IntegerProperty, RelationshipFrom,
        RelationshipTo, StructuredRel, DateTimeProperty)
from neomodel.match import NodeSet, QueryBuilder
from neomodel.exception import MultipleNodesReturned
from datetime import datetime


class SupplierRel(StructuredRel):
    since = DateTimeProperty(default=datetime.now)


class Supplier(StructuredNode):
    name = StringProperty()
    delivery_cost = IntegerProperty()
    coffees = RelationshipTo('Coffee', 'SUPPLIES')


class Coffee(StructuredNode):
    name = StringProperty(unique_index=True)
    price = IntegerProperty()
    suppliers = RelationshipFrom(Supplier, 'SUPPLIES', model=SupplierRel)


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
    assert 'SUPPLIES' in qb._ast['where'][0]
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

    try:
        Coffee.nodes.get(name='2')
    except Coffee.DoesNotExist:
        assert True
    else:
        assert False

    Coffee(name='2', price=3).save()

    try:
        Coffee.nodes.get(price=3)
    except MultipleNodesReturned:
        assert True
    else:
        assert False


def test_simple_traverse_with_filter():
    nescafe = Coffee(name='Nescafe2', price=99).save()
    tesco = Supplier(name='Sainsburys', delivery_cost=2).save()
    nescafe.suppliers.connect(tesco)

    qb = QueryBuilder(NodeSet(source=nescafe).suppliers.match(since__lt=datetime.now()))

    results = qb.build_ast()._execute()

    assert 'start' in qb._ast
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
    assert len(Coffee.nodes[1]) == 1
    assert len(Coffee.nodes[0]) == 1
    assert len(Coffee.nodes[1:2]) == 1


def test_contains():
    expensive = Coffee(price=1000, name="Pricey").save()
    asda = Coffee(name='Asda', price=1).save()

    assert expensive in Coffee.nodes.filter(price__gt=999)
    assert asda not in Coffee.nodes.filter(price__gt=999)

    # bad value raises
    try:
        2 in Coffee.nodes
    except ValueError:
        assert True
    else:
        assert False

    # unsaved
    try:
        Coffee() in Coffee.nodes
    except ValueError:
        assert True
    else:
        assert False
