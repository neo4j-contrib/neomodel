from neomodel import AsyncRelationshipTo, AsyncStructuredNode, StringProperty
from neomodel.test_relationships import Country


class Cat(AsyncStructuredNode):
    name = StringProperty()
    # Relationship is defined using a relative class path
    is_from = AsyncRelationshipTo(".test_relationships.Country", "IS_FROM")


def test_relative_relationship():
    a = Cat(name="snufkin").save()
    assert a

    c = Country(code="MG").save()
    assert c

    # connecting an instance of the class defined above
    # the next statement will fail if there's a type mismatch
    a.is_from.connect(c)
    assert a.is_from.is_connected(c)
