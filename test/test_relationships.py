from neomodel import NeoNode, StringProperty, IntegerProperty, OUTGOING, INCOMING
from neomodel.core import connection_adapter


class Country(NeoNode):
    code = StringProperty(unique_index=True)


class Person(NeoNode):
    name = StringProperty(unique_index=True)
    age = IntegerProperty(index=True)


Person.relate('is_from', (OUTGOING, 'IS_FROM'), to=Country)
Country.relate('inhabitant', (INCOMING, 'IS_FROM'), to=Person)


def setup():
    connection_adapter().client.clear()


def test_bidirectional_relationships():
    u = Person(name='Jim', age=3).save()
    assert u

    de = Country(code='DE').save()
    assert de

    assert u.is_from.__class__.__name__ == 'ZeroOrMore'
    u.is_from.connect(de)

    assert u.is_from.is_connected(de)

    b = u.is_from.all()[0]
    assert b.__class__.__name__ == 'Country'
    assert b.code == 'DE'

    s = b.inhabitant.all()[0]
    assert s.name == 'Jim'

    u.is_from.disconnect(b)

    assert not u.is_from.all()
    assert not u.is_from.is_connected(b)
