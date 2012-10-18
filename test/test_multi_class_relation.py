from neomodel import StructuredNode, StringProperty, RelationshipTo


class Humanbeing(StructuredNode):
    name = StringProperty(unique_index=True)
    has_a = RelationshipTo(['Location', 'Nationality'], 'HAS_A')


class Location(StructuredNode):
    name = StringProperty(unique_index=True)


class Nationality(StructuredNode):
    name = StringProperty(unique_index=True)


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


def test_multi_class_search():
    foo = Humanbeing(name='foo').save()
    lo = Location(name='Birmingham').save()
    na = Nationality(name='Croatian').save()
    na2 = Nationality(name='French').save()

    foo.has_a.connect(lo)
    foo.has_a.connect(na)
    foo.has_a.connect(na2)

    results = foo.has_a.search(name='French')
    assert isinstance(results[0], Nationality)
    results = foo.has_a.search(name='Birmingham')
    assert isinstance(results[0], Location)
