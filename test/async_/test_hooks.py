from test._async_compat import mark_async_test

from neomodel import AsyncStructuredNode, StringProperty

HOOKS_CALLED = {}


class HookTest(AsyncStructuredNode):
    name = StringProperty()

    def post_create(self):
        HOOKS_CALLED["post_create"] = 1

    def pre_save(self):
        HOOKS_CALLED["pre_save"] = 1

    def post_save(self):
        HOOKS_CALLED["post_save"] = 1

    def pre_delete(self):
        HOOKS_CALLED["pre_delete"] = 1

    def post_delete(self):
        HOOKS_CALLED["post_delete"] = 1


@mark_async_test
async def test_hooks():
    ht = await HookTest(name="k").save()
    await ht.delete()
    assert "pre_save" in HOOKS_CALLED
    assert "post_save" in HOOKS_CALLED
    assert "post_create" in HOOKS_CALLED
    assert "pre_delete" in HOOKS_CALLED
    assert "post_delete" in HOOKS_CALLED
