from neomodel import AliasProperty, StringProperty, StructuredNode


class MagicProperty(AliasProperty):
    def setup(self):
        self.owner.setup_hook_called = True


class AliasTestNode(StructuredNode):
    name = StringProperty(unique_index=True)
    full_name = AliasProperty(to="name")
    long_name = MagicProperty(to="name")


def test_property_setup_hook():
    tim = AliasTestNode(long_name="tim").save()
    assert AliasTestNode.setup_hook_called
    assert tim.name == "tim"


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
