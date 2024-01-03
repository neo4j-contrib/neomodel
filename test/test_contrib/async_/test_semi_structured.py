from test._async_compat import mark_async_test

from neomodel import IntegerProperty, StringProperty
from neomodel.contrib import AsyncSemiStructuredNode


class UserProf(AsyncSemiStructuredNode):
    email = StringProperty(unique_index=True, required=True)
    age = IntegerProperty(index=True)


class Dummy(AsyncSemiStructuredNode):
    pass


@mark_async_test
async def test_to_save_to_model_with_required_only():
    u = UserProf(email="dummy@test.com")
    assert await u.save()


@mark_async_test
async def test_save_to_model_with_extras():
    u = UserProf(email="jim@test.com", age=3, bar=99)
    u.foo = True
    assert await u.save()
    u = await UserProf.nodes.get(age=3)
    assert u.foo is True
    assert u.bar == 99


@mark_async_test
async def test_save_empty_model():
    dummy = Dummy()
    assert await dummy.save()
