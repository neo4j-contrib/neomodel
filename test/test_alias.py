from neomodel import StructuredNode, StringProperty, AliasProperty


class MagicProperty(AliasProperty):
    def setup(self):
        self.owner.setup_hook_called = True


class AliasTestNode(StructuredNode):
    name = StringProperty(unique_index=True)
    full_name = AliasProperty(to='name')
    long_name = MagicProperty(to='name')


def test_property_setup_hook():
    assert AliasTestNode.setup_hook_called


def test_alias():
    jim = AliasTestNode(full_name='Jim')
    assert 'name' in jim.__property_definitions__
    assert 'name' not in jim.__alias_definitions__
    assert 'full_name' not in jim.__properties__
    assert 'full_name' in jim.__alias_definitions__
    assert jim.name is jim.__properties__['name']
    assert isinstance(jim.name, str), type(jim.name)
    assert jim.name == 'Jim'
    assert jim.full_name == 'Jim'
    jim.save()
    assert jim.name == 'Jim'
    assert jim.full_name == 'Jim'
    assert 'full_name' not in AliasTestNode.deflate(jim.__properties__)
    jim = AliasTestNode.nodes.get(full_name='Jim')
    assert jim
    assert jim.name == 'Jim'
    assert jim.full_name == 'Jim'
    assert 'full_name' not in AliasTestNode.deflate(jim.__properties__)
