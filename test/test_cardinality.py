from pytest import raises

from neomodel import (StructuredNode, StringProperty, IntegerProperty, OneOrMore, ZeroOrMore,
                      RelationshipTo, AttemptedCardinalityViolation, CardinalityViolation,
                      ZeroOrOne, One)


class HairDryer(StructuredNode):
    version = IntegerProperty()


class ScrewDriver(StructuredNode):
    version = IntegerProperty()


class Car(StructuredNode):
    version = IntegerProperty()


class Monkey(StructuredNode):
    name = StringProperty()
    dryers = RelationshipTo('HairDryer', 'OWNS_DRYER', cardinality=ZeroOrMore)
    driver = RelationshipTo('ScrewDriver', 'HAS_SCREWDRIVER', cardinality=ZeroOrOne)
    car = RelationshipTo('Car', 'HAS_CAR', cardinality=OneOrMore)
    toothbrush = RelationshipTo('ToothBrush', 'HAS_TOOTHBRUSH', cardinality=One)


class ToothBrush(StructuredNode):
    name = StringProperty()


def test_cardinality_zero_or_more():
    m = Monkey(name='tim').save()
    assert m.dryers.all() == []
    assert m.dryers.single() is None
    h = HairDryer(version=1).save()

    m.dryers.connect(h)
    assert len(m.dryers.all()) == 1
    assert m.dryers.single().version == 1

    m.dryers.disconnect(h)
    assert m.dryers.all() == []
    assert m.dryers.single() is None


def test_cardinality_zero_or_one():
    m = Monkey(name='bob').save()
    assert m.driver.all() == []
    assert m.driver.single() is None
    h = ScrewDriver(version=1).save()

    m.driver.connect(h)
    assert len(m.driver.all()) == 1
    assert m.driver.single().version == 1

    j = ScrewDriver(version=2).save()
    with raises(AttemptedCardinalityViolation):
        m.driver.connect(j)

    m.driver.reconnect(h, j)
    assert m.driver.single().version == 2


def test_cardinality_one_or_more():
    m = Monkey(name='jerry').save()

    with raises(CardinalityViolation):
        m.car.all()

    with raises(CardinalityViolation):
        m.car.single()

    c = Car(version=2).save()
    m.car.connect(c)
    assert m.car.single().version == 2

    with raises(AttemptedCardinalityViolation):
        m.car.disconnect(c)


def test_cardinality_one():
    m = Monkey(name='jerry').save()

    with raises(CardinalityViolation):
        m.toothbrush.all()

    with raises(CardinalityViolation):
        m.toothbrush.single()

    b = ToothBrush(name='Jim').save()
    m.toothbrush.connect(b)
    assert m.toothbrush.single().name == 'Jim'

    x = ToothBrush(name='Jim').save
    with raises(AttemptedCardinalityViolation):
        m.toothbrush.connect(x)

    with raises(AttemptedCardinalityViolation):
        m.toothbrush.disconnect(b)
