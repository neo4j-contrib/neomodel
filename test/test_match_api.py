from neomodel import (StructuredNode, StringProperty, IntegerProperty, RelationshipFrom,
        RelationshipTo, StructuredRel, DateTimeProperty)
from neomodel.match import NodeSet, QueryBuilder, Traversal
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
    node_set = NodeSet(Coffee)
    qb = QueryBuilder(node_set)
    qb.build_ast()
    assert '(coffee:Coffee)' in qb._ast['match']

    # with filter and exclude
    node_set = node_set.filter(price__gt=2).exclude(price__gt=6, name='Java')
    qb = QueryBuilder(node_set)
    qb.build_ast()
    assert '(coffee:Coffee)' in qb._ast['match']
    assert 'NOT' in qb._ast['where'][1]


def test_simple_has_via_label():
    ns = NodeSet(Coffee).has(suppliers=True)
    qb = QueryBuilder(ns)
    qb.build_ast()
    assert 'SUPPLIES' in qb._ast['match'][1]

    ns = NodeSet(Coffee).has(suppliers=False)
    qb = QueryBuilder(ns)
    qb.build_ast()
    assert 'NOT' in qb._ast['where'][0]


def test_simple_traverse():
    latte = Coffee(name="Latte").save()
    traversal = Traversal(source=latte,
        key='suppliers',
        definition=Coffee.suppliers.definition).match(since__lt=datetime.now())

    qb = QueryBuilder(NodeSet(source=traversal))
    qb.build_ast()
    print repr(qb._ast)
