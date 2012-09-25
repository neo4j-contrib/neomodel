from neomodel import StructuredNode, StringProperty, IntegerProperty
from neomodel.core import connection_adapter


class Country(StructuredNode):
    code = StringProperty(unique_index=True)


class Person(StructuredNode):
    name = StringProperty(unique_index=True)
    age = IntegerProperty(index=True)


class SuperHero(Person):
    power = StringProperty(index=True)

Person.outgoing('IS_FROM', 'is_from', to=Country)
Country.incoming('IS_FROM', 'inhabitant', to=Person)


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


def test_abstract_class_relationships():
    j = Person(name='Joe', age=13).save()
    assert j

    u = SuperHero(name='UltraJoe', age=13, power='invisibility').save()
    assert u

    gr = Country(code='GR').save()
    assert gr

    gr.inhabitant.connect(j)
    assert gr.inhabitant.is_connected(j)

    gr.inhabitant.connect(u)
    assert gr.inhabitant.is_connected(u)
