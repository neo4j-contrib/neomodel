from neomodel import StructuredNode, StringProperty, IntegerProperty
from neomodel.core import connection_adapter
from lucenequerybuilder import Q


class Human(StructuredNode):
    name = StringProperty(unique_index=True, optional=True)
    age = IntegerProperty(index=True, optional=True)


def setup():
    connection_adapter().client.clear()


def test_optional_properties_dont_get_indexed():
    Human(name=None, age=99).save()
    h = Human.index.get(age=99)
    assert h
    assert h.name is None

    Human(age=98).save()
    h = Human.index.get(age=98)
    assert h
    assert h.name is None


def test_lucene_query():
    Human(name='sarah', age=3).save()
    Human(name='jim', age=4).save()
    Human(name='bob', age=5).save()
    Human(name='tim', age=2).save()

    names = [p.name for p in Human.index.search(Q('age', inrange=[3, 5]))]
    assert 'sarah' in names
    assert 'jim' in names
    assert 'bob' in names
