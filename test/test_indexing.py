from neomodel.core import NeoNode, StringProperty, IntegerProperty, connection_adapter
from lucenequerybuilder import Q


class Human(NeoNode):
    name = StringProperty(unique_index=True)
    age = IntegerProperty(index=True)


def setup():
    connection_adapter().client.clear()


def test_lucene_query():
    Human(name='sarah', age=3).save()
    Human(name='jim', age=4).save()
    Human(name='bob', age=5).save()
    Human(name='tim', age=2).save()

    names = [p.name for p in Human.index.search(Q('age', inrange=[3, 5]))]
    assert 'sarah' in names
    assert 'jim' in names
    assert 'bob' in names
