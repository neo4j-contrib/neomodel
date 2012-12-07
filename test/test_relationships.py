from neomodel import *
from neomodel.contrib import Hierarchical, Multilingual, Language


class Person(Multilingual, StructuredNode):
    name = StringProperty(unique_index=True)
    age = IntegerProperty(index=True)
    is_from = RelationshipTo('Country', 'IS_FROM')

    @property
    def special_name(self):
        return self.name

    def special_power(self):
        return "I have no powers"


class Country(Hierarchical, StructuredNode):
    code = StringProperty(unique_index=True)
    inhabitant = RelationshipFrom('Person', 'IS_FROM')


class Nationality(Hierarchical, StructuredNode):
    code = StringProperty(unique_index=True)


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

    assert u.is_from.__class__.__name__ == 'ZeroOrMore'
    u.is_from.connect(de)

    assert len(u.is_from) == 1

    assert u.is_from.is_connected(de)

    b = u.is_from.all()[0]
    assert b.__class__.__name__ == 'Country'
    assert b.code == 'DE'

    s = b.inhabitant.all()[0]
    assert s.name == 'Jim'

    u.is_from.disconnect(b)

    assert not u.is_from.all()
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


def test_hierarchies():
    gb = Country(code="GB").save()
    print "GB node = {0}".format(gb.__node__)
    cy = Country(code="CY").save()
    british = Nationality(__parent__=gb, code="GB-GB").save()
    greek_cypriot = Nationality(__parent__=cy, code="CY-GR").save()
    turkish_cypriot = Nationality(__parent__=cy, code="CY-TR").save()
    assert british.parent() == gb
    assert greek_cypriot.parent() == cy
    assert turkish_cypriot.parent() == cy
    assert greek_cypriot in cy.children(Nationality)


def test_multilingual():
    bob = Person(name="Bob", age=77).save()
    bob.attach_language(Language.get("fr"))
    bob.attach_language("ar")
    bob.attach_language(Language.get("ar"))
    bob.attach_language(Language.get("pl"))
    print "Multilingual bob is node " + str(bob.__node__)
    assert bob.has_language("fr")
    assert not bob.has_language("es")
    bob.detach_language("fr")
    assert not bob.has_language("fr")
    assert len(bob.languages()) == 2
    assert Language.get("pl") in bob.languages()
    assert Language.get("ar") in bob.languages()
