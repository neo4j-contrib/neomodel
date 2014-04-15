from neomodel import (StructuredNode, StringProperty, IntegerProperty, RelationshipFrom,
        RelationshipTo, StructuredRel, DateTimeProperty)
from neomodel.match import NodeSet, QueryBuilder
from datetime import datetime


class SupplierRel(StructuredRel):
    since = DateTimeProperty(default=datetime.now)


class Supplier(StructuredNode):
    name = StringProperty()
    delivery_cost = IntegerProperty()
    coffees = RelationshipTo('Coffee', 'SUPPLIES')


class Coffee(StructuredNode):
    name = StringProperty()
    price = IntegerProperty()
    suppliers = RelationshipFrom(Supplier, 'SUPPLIES', model=SupplierRel)


def test_filter_exclude_via_labels():
    Coffee(name='Java', price=99).save()

    node_set = NodeSet(Coffee)
    qb = QueryBuilder(node_set)

    results = qb.execute()

    assert '(coffee:Coffee)' in qb._ast['match']
    assert 'result_class' in qb._ast
    assert len(results) == 1
    assert isinstance(results[0], Coffee)
    assert results[0].name == 'Java'

    # with filter and exclude
    Coffee(name='Kenco', price=3).save()
    node_set = node_set.filter(price__gt=2).exclude(price__gt=6, name='Java')
    qb = QueryBuilder(node_set)

    results = qb.execute()
    assert '(coffee:Coffee)' in qb._ast['match']
    assert 'NOT' in qb._ast['where'][0]
    assert len(results) == 1
    assert results[0].name == 'Kenco'


def test_simple_has_via_label():
    nescafe = Coffee(name='Nescafe', price=99).save()
    tesco = Supplier(name='Tesco', delivery_cost=2).save()
    nescafe.suppliers.connect(tesco)

    ns = NodeSet(Coffee).has(suppliers=True)
    qb = QueryBuilder(ns)
    results = qb.execute()
    assert 'SUPPLIES' in qb._ast['where'][0]
    assert len(results) == 1
    assert results[0].name == 'Nescafe'

    Coffee(name='nespresso', price=99).save()
    ns = NodeSet(Coffee).has(suppliers=False)
    qb = QueryBuilder(ns)
    results = qb.execute()
    assert len(results) > 0
    assert 'NOT' in qb._ast['where'][0]


def test_simple_traverse_with_filter():
    nescafe = Coffee(name='Nescafe', price=99).save()
    tesco = Supplier(name='Tesco', delivery_cost=2).save()
    nescafe.suppliers.connect(tesco)

    qb = QueryBuilder(NodeSet(source=nescafe).suppliers.match(since__lt=datetime.now()))

    results = qb.execute()

    assert 'start' in qb._ast
    assert 'match' in qb._ast
    assert qb._ast['return'] == 'suppliers'
    assert len(results) == 1
    assert results[0].name == 'Tesco'
