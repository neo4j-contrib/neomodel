from neomodel import StructuredNode, StringProperty, IntegerProperty
from neomodel.match import NodeSet, QueryBuilder


class Coffee(StructuredNode):
    name = StringProperty()
    price = IntegerProperty()


def setup():
    Coffee(name="Latte").save()


def test_match_labels():
    node_set = NodeSet(Coffee)
    qb = QueryBuilder(node_set).build_ast()
    assert '(coffee:Coffee)' in qb._ast['match']

    # with filter
    node_set = node_set.filter(price__gt=2).exclude(price__gt=6, name='Java')
    qb = QueryBuilder(node_set).build_ast()
    assert '(coffee:Coffee)' in qb._ast['match']
    assert 'NOT' in qb._ast['where'][1]
