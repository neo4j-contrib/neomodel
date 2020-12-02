from pytest import raises

from neomodel import (StructuredNode, RelationshipTo, RelationshipFrom, Relationship,
                      StringProperty, IntegerProperty, StructuredRel, One, Traversal)


class PersonWithRels(StructuredNode):
    name = StringProperty(unique_index=True)
    age = IntegerProperty(index=True)
    is_from = RelationshipTo('Country', 'IS_FROM')
    knows = Relationship(u'PersonWithRels', 'KNOWS')  # use unicode to check issue

    @property
    def special_name(self):
        return self.name

    def special_power(self):
        return "I have no powers"


class Country(StructuredNode):
    code = StringProperty(unique_index=True)
    inhabitant = RelationshipFrom(PersonWithRels, 'IS_FROM')
    president = RelationshipTo(PersonWithRels, 'PRESIDENT', cardinality=One)


class SuperHero(PersonWithRels):
    power = StringProperty(index=True)

    def special_power(self):
        return "I have powers"


def test_actions_on_deleted_node():
    u = PersonWithRels(name='Jim2', age=3).save()
    u.delete()
    with raises(ValueError):
        u.is_from.connect(None)

    with raises(ValueError):
        u.is_from.get()

    with raises(ValueError):
        u.save()


def test_bidirectional_relationships():
    u = PersonWithRels(name='Jim', age=3).save()
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


def test_either_direction_connect():
    rey = PersonWithRels(name='Rey', age=3).save()
    sakis = PersonWithRels(name='Sakis', age=3).save()

    rey.knows.connect(sakis)
    assert rey.knows.is_connected(sakis)
    assert sakis.knows.is_connected(rey)
    sakis.knows.connect(rey)

    result, meta = sakis.cypher("""MATCH (us), (them)
            WHERE id(us)=$self and id(them)=$them
            MATCH (us)-[r:KNOWS]-(them) RETURN COUNT(r)""",
            {'them': rey.id})
    assert int(result[0][0]) == 1

    rel = rey.knows.relationship(sakis)
    assert isinstance(rel, StructuredRel)

    rels = rey.knows.all_relationships(sakis)
    assert isinstance(rels[0], StructuredRel)


def test_search_and_filter_and_exclude():
    fred = PersonWithRels(name='Fred', age=13).save()
    zz = Country(code='ZZ').save()
    zx = Country(code='ZX').save()
    zt = Country(code='ZY').save()
    fred.is_from.connect(zz)
    fred.is_from.connect(zx)
    fred.is_from.connect(zt)
    result = fred.is_from.filter(code='ZX')
    assert result[0].code == 'ZX'

    result = fred.is_from.filter(code='ZX')
    assert result[0].code == 'ZX'

    result = fred.is_from.exclude(code='ZZ').exclude(code='ZY')
    assert result[0].code == 'ZX' and len(result) == 1


def test_custom_methods():
    u = PersonWithRels(name='Joe90', age=13).save()
    assert u.special_power() == "I have no powers"
    u = SuperHero(name='Joe91', age=13, power='xxx').save()
    assert u.special_power() == "I have powers"
    assert u.special_name == 'Joe91'


def test_valid_reconnection():
    p = PersonWithRels(name='ElPresidente', age=93).save()
    assert p

    pp = PersonWithRels(name='TheAdversary', age=33).save()
    assert pp

    c = Country(code='CU').save()
    assert c

    c.president.connect(p)
    assert c.president.is_connected(p)

    # the coup d'etat
    c.president.reconnect(p, pp)
    assert c.president.is_connected(pp)

    # reelection time
    c.president.reconnect(pp, pp)
    assert c.president.is_connected(pp)


def test_valid_replace():
    brady = PersonWithRels(name='Tom Brady', age=40).save()
    assert brady

    gronk = PersonWithRels(name='Rob Gronkowski', age=28).save()
    assert gronk

    colbert = PersonWithRels(name='Stephen Colbert', age=53).save()
    assert colbert

    hanks = PersonWithRels(name='Tom Hanks', age=61).save()
    assert hanks

    brady.knows.connect(gronk)
    brady.knows.connect(colbert)
    assert len(brady.knows) == 2
    assert brady.knows.is_connected(gronk)
    assert brady.knows.is_connected(colbert)

    brady.knows.replace(hanks)
    assert len(brady.knows) == 1
    assert brady.knows.is_connected(hanks)
    assert not brady.knows.is_connected(gronk)
    assert not brady.knows.is_connected(colbert)


def test_props_relationship():
    u = PersonWithRels(name='Mar', age=20).save()
    assert u

    c = Country(code='AT').save()
    assert c

    c2 = Country(code='LA').save()
    assert c2

    with raises(NotImplementedError):
        c.inhabitant.connect(u, properties={'city': 'Thessaloniki'})


def test_multiple_label_relationship_traversal():
    #set up country and two persons
    p1 = PersonWithRels(name="Max", age=20).save()
    p2 = PersonWithRels(name="Moritz", age=21).save()
    c1 = Country(code="IO").save()

    assert p1
    assert p2
    assert c1

    c1.inhabitant.connect(p1)
    c1.president.connect(p2)

    assert len(c1.inhabitant) == 1
    assert len(c1.president) == 1

    # test that both inhabitant and president is returned when specifying both
    definition = dict(node_class=PersonWithRels, direction=None,
                      relation_type=('IS_FROM', 'PRESIDENT'), model=None)
    relations_traversal = Traversal(c1, PersonWithRels.__label__,
                                    definition)

    assert len(relations_traversal) == 2

    assert p1 in relations_traversal
    assert p2 in relations_traversal

    # add president as inhabitant
    c1.inhabitant.connect(p2)

    # test that we still get only two results from the same traversal
    relations_traversal = Traversal(c1, PersonWithRels.__label__,
                                    definition)

    # p2 is connected twice, but should only be returned once
    assert len(relations_traversal) == 2

    assert p1 in relations_traversal
    assert p2 in relations_traversal

    # check if lazy evaluation also honors the distinct restriction
    lazy_evaluated = Traversal(c1, PersonWithRels.__label__, definition).all(True)

    assert len(lazy_evaluated) == 2

    assert p1.id in lazy_evaluated
    assert p2.id in lazy_evaluated
