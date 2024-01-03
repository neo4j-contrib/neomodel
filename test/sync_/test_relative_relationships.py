from test._async_compat import mark_sync_test
from test.sync_.test_relationships import Country

from neomodel import RelationshipTo, StringProperty, StructuredNode


class Cat(StructuredNode):
    name = StringProperty()
    # Relationship is defined using a relative class path
    is_from = RelationshipTo(".test_relationships.Country", "IS_FROM")


@mark_sync_test
def test_relative_relationship():
    a = Cat(name="snufkin").save()
    assert a

    c = Country(code="MG").save()
    assert c

    # connecting an instance of the class defined above
    # the next statement will fail if there's a type mismatch
    a.is_from.connect(c)
    assert a.is_from.is_connected(c)
