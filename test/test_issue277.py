from neomodel import StructuredNode, StructuredRel, StringProperty, UniqueIdProperty, RelationshipTo, NodeSet


class SomeRel(StructuredRel):
    prop = StringProperty()


class SomeNode(StructuredNode):
    identifier = UniqueIdProperty()

    connected_to = RelationshipTo('SomeNode', 'CONNECTED', model=SomeRel)


def test_rel_match_returns_node_set():
    a = SomeNode()
    a.save()

    assert type(a.connected_to.match(prop="asdf")) is NodeSet
