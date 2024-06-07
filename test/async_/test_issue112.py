from test._async_compat import mark_async_test

from neomodel import AsyncRelationshipTo, AsyncStructuredNode


class SomeModel(AsyncStructuredNode):
    test = AsyncRelationshipTo("SomeModel", "SELF")


@mark_async_test
async def test_len_relationship():
    t1 = await SomeModel().save()
    t2 = await SomeModel().save()

    await t1.test.connect(t2)
    l = len(await t1.test.all())

    assert l
    assert l == 1
