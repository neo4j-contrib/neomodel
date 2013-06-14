from neomodel import (StructuredNode, RelationshipTo, RelationshipFrom,
        StringProperty, IntegerProperty)


class Person(StructuredNode):
    name = StringProperty(unique_index=True)
    age = IntegerProperty(index=True)
    is_from = RelationshipTo('Country', 'IS_FROM')

    @property
    def special_name(self):
        return self.name

    def special_power(self):
        return "I have no powers"


class Country(StructuredNode):
    code = StringProperty(unique_index=True)
    inhabitant = RelationshipFrom(Person, 'IS_FROM')


class SuperHero(Person):
    power = StringProperty(index=True)

    def special_power(self):
        return "I have powers"


def test_bidirectional_relationships():
    u = Person(name='Jim', age=3).save()
    assert u

    de = Country(code='DE').save()
    assert de

    assert len(u.is_from) == 0
    assert not u.is_from

    assert u.is_from.__class__.__name__ == 'ZeroOrMore'
    u.is_from.connect(de)

    assert len(u.is_from) == 1
    assert u.is_from

    assert u.is_from.is_connected(de)

    b = u.is_from.all()[0]
    assert b.__class__.__name__ == 'Country'
    assert b.code == 'DE'

    s = b.inhabitant.all()[0]
    assert s.name == 'Jim'

    u.is_from.disconnect(b)
    assert not u.is_from.is_connected(b)


def test_search():
    fred = Person(name='Fred', age=13).save()
    zz = Country(code='ZZ').save()
    zx = Country(code='ZX').save()
    zt = Country(code='ZY').save()
    fred.is_from.connect(zz)
    fred.is_from.connect(zx)
    fred.is_from.connect(zt)
    result = fred.is_from.search(code='ZX')
    assert result[0].code == 'ZX'


def test_custom_methods():
    u = Person(name='Joe90', age=13).save()
    assert u.special_power() == "I have no powers"
    u = SuperHero(name='Joe91', age=13, power='xxx').save()
    assert u.special_power() == "I have powers"
    assert u.special_name == 'Joe91'


def test_props_relationship():
    u = Person(name='Mar', age=20).save()
    assert u

    c = Country(code='AT').save()
    assert c

    c2 = Country(code='LA').save()
    assert c2

    c.inhabitant.connect(u, properties={'city': 'Thessaloniki'})
    assert c.inhabitant.is_connected(u)

    # Check if properties were inserted
    result = u.cypher('START root=node:Person(name={name})' +
        ' MATCH root-[r:IS_FROM]->() RETURN r.city', {'name': u.name})[0]
    assert result and result[0][0] == 'Thessaloniki'

    u.is_from.reconnect(c, c2)
    assert u.is_from.is_connected(c2)

    # Check if properties are transferred correctly
    result = u.cypher('START root=node:Person(name={name})' +
        ' MATCH root-[r:IS_FROM]->() RETURN r.city', {'name': u.name})[0]
    assert result and result[0][0] == 'Thessaloniki'
