from neomodel import RelationshipTo, StringProperty, StructuredNodeAsync
from neomodel.test_relationships import Country


class Cat(StructuredNodeAsync):
    name = StringProperty()
    # Relationship is defined using a relative class path
    is_from = RelationshipTo(".test_relationships.Country", "IS_FROM")


def test_relative_relationship():
    a = Cat(name="snufkin").save_async()
    assert a

    c = Country(code="MG").save_async()
    assert c

    # connecting an instance of the class defined above
    # the next statement will fail if there's a type mismatch
    a.is_from.connect(c)
    assert a.is_from.is_connected(c)
