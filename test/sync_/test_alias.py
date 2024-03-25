from test._async_compat import mark_sync_test

from neomodel import AliasProperty, StringProperty, StructuredNode


class MagicProperty(AliasProperty):
    def setup(self):
        self.owner.setup_hook_called = True


class AliasTestNode(StructuredNode):
    name = StringProperty(unique_index=True)
    full_name = AliasProperty(to="name")
    long_name = MagicProperty(to="name")


@mark_sync_test
def test_property_setup_hook():
    timmy = AliasTestNode(long_name="timmy").save()
    assert AliasTestNode.setup_hook_called
    assert timmy.name == "timmy"


@mark_sync_test
def test_alias():
    jim = AliasTestNode(full_name="Jim").save()
    assert jim.name == "Jim"
    assert jim.full_name == "Jim"
    assert "full_name" not in AliasTestNode.deflate(jim.__properties__)
    jim = AliasTestNode.nodes.get(full_name="Jim")
    assert jim
    assert jim.name == "Jim"
    assert jim.full_name == "Jim"
    assert "full_name" not in AliasTestNode.deflate(jim.__properties__)
