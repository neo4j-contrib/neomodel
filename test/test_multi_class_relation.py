from neomodel import StructuredNode, StringProperty
from neomodel.core import connection_adapter


class Humanbeing(StructuredNode):
    name = StringProperty(unique_index=True)


class Location(StructuredNode):
    name = StringProperty(unique_index=True)


class Nationality(StructuredNode):
    name = StringProperty(unique_index=True)


Humanbeing.outgoing('HAS_A', 'has_a', to=[Location, Nationality])


def setup():
    connection_adapter().client.clear()


def test_multi_class_rels():
    ne = Humanbeing(name='new news').save()
    lo = Location(name='Belgium').save()
    na = Nationality(name='British').save()

    ne.has_a.connect(lo)
    ne.has_a.connect(na)

    results = ne.has_a.all()
    assert len(results) == 2
    assert isinstance(results[0], Location)
    assert results[0].name == 'Belgium'
    assert isinstance(results[1], Nationality)
    assert results[1].name == 'British'
