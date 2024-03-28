from test._async_compat import mark_async_test
from test.async_.test_relationships import Country

from neomodel import AsyncRelationshipTo, AsyncStructuredNode, StringProperty


class Cat(AsyncStructuredNode):
    name = StringProperty()
    # Relationship is defined using a relative class path
    is_from = AsyncRelationshipTo(".test_relationships.Country", "IS_FROM")


@mark_async_test
async def test_relative_relationship():
    a = await Cat(name="snufkin").save()
    assert a

    c = await Country(code="MG").save()
    assert c

    # connecting an instance of the class defined above
    # the next statement will fail if there's a type mismatch
    await a.is_from.connect(c)
    assert await a.is_from.is_connected(c)
