from test.async__compat import mark_async_test

from neomodel import AliasProperty, AsyncStructuredNode, StringProperty


class MagicProperty(AliasProperty):
    def setup(self):
        self.owner.setup_hook_called = True


class AliasTestNode(AsyncStructuredNode):
    name = StringProperty(unique_index=True)
    full_name = AliasProperty(to="name")
    long_name = MagicProperty(to="name")


@mark_async_test
async def test_property_setup_hook():
    tim = await AliasTestNode(long_name="tim").save()
    assert AliasTestNode.setup_hook_called
    assert tim.name == "tim"


@mark_async_test
async def test_alias():
    jim = await AliasTestNode(full_name="Jim").save()
    assert jim.name == "Jim"
    assert jim.full_name == "Jim"
    assert "full_name" not in AliasTestNode.deflate(jim.__properties__)
    jim = await AliasTestNode.nodes.get(full_name="Jim")
    assert jim
    assert jim.name == "Jim"
    assert jim.full_name == "Jim"
    assert "full_name" not in AliasTestNode.deflate(jim.__properties__)
