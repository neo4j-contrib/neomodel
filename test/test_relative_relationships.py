from neomodel import RelationshipTo, StringProperty, StructuredNode

from .test_relationships import Country


class Cat(StructuredNode):
    name = StringProperty()
    # Relationship is defined using a relative class path
    is_from = RelationshipTo(".test_relationships.Country", "IS_FROM")


def test_relative_relationship():
    a = Cat(name="snufkin").save()
    assert a

    c = Country(code="MG").save()
    assert c

    # connecting an instance of the class defined above
    # the next statement will fail if there's a type mismatch
    a.is_from.connect(c)
    assert a.is_from.is_connected(c)
