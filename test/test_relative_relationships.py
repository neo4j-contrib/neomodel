from neomodel import StructuredNode, RelationshipTo, StringProperty
from .test_relationships import Country


class Cat(StructuredNode):
    name = StringProperty()
    is_from = RelationshipTo('.test_relationships.Country', 'IS_FROM')


def test_relative_relationship():
    a = Cat(name='snufkin').save()
    assert a

    c = Country(code='MG').save()
    assert c

    a.is_from.connect(c)
    assert a.is_from.is_connected(c)
