from neomodel.core import NeoNode, StringProperty, IntegerProperty, Relationship, connection_adapter


class Country(NeoNode):
    code = StringProperty(unique_index=True)


class Person(NeoNode):
    name = StringProperty(unique_index=True)
    age = IntegerProperty(index=True)
    is_from = Relationship('IS_FROM', Country)


def setup():
    connection_adapter().client.clear()
    Person.deploy()
    Country.deploy()


def test_local_relationship():
    u = Person(name='Jim', age=3).save()
    assert u

    de = Country(code='DE').save()
    assert de

    assert u.is_from.__class__.__name__ == 'RelationshipManager'
    u.is_from.relate(de)

    assert u.is_from.is_related(de)

    b = u.is_from.all()[0]
    assert b.__class__.__name__ == 'Country'
    assert b.code == 'DE'

    u.is_from.unrelate(b)

    assert not u.is_from.all()
    assert not u.is_from.is_related(b)
