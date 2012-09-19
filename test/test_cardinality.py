from neomodel import (NeoNode, StringProperty, IntegerProperty, OUTGOING,
        OneOrMore, ZeroOrMore, ZeroOrOne, One, AttemptedCardinalityViolation, CardinalityViolation)
from neomodel.core import connection_adapter


class HairDryer(NeoNode):
    version = IntegerProperty()


class ScrewDriver(NeoNode):
    version = IntegerProperty()


class Car(NeoNode):
    version = IntegerProperty()


class Monkey(NeoNode):
    name = StringProperty()


class ToothBrush(NeoNode):
    name = StringProperty()


def setup():
    connection_adapter().client.clear()


def test_cardinality_zero_or_more():
    Monkey.relate('dryers', ('OWNS_DRYER', OUTGOING), to=HairDryer, cardinality=ZeroOrMore)

    m = Monkey(name='tim').save()
    assert m.dryers.all() == []
    assert m.dryers.single() == None
    h = HairDryer(version=1).save()

    m.dryers.relate(h)
    assert len(m.dryers.all()) == 1
    assert m.dryers.single().version == 1

    m.dryers.unrelate(h)
    assert m.dryers.all() == []
    assert m.dryers.single() == None


def test_cardinality_zero_or_one():
    Monkey.relate('driver', ('HAS_SCREWDRIVER', OUTGOING), to=ScrewDriver, cardinality=ZeroOrOne)

    m = Monkey(name='bob').save()
    assert m.driver.all() == []
    assert m.driver.single() == None
    h = ScrewDriver(version=1).save()

    m.driver.relate(h)
    assert len(m.driver.all()) == 1
    assert m.driver.single().version == 1

    j = ScrewDriver(version=2).save()
    try:
        m.driver.relate(j)
    except AttemptedCardinalityViolation:
        assert True
    else:
        assert False

    m.driver.rerelate(h, j)
    assert m.driver.single().version == 2


def test_cardinality_one_or_more():
    Monkey.relate('car', ('HAS_CAR', OUTGOING), to=Car, cardinality=OneOrMore)
    m = Monkey(name='jerry').save()

    try:
        m.car.all()
    except CardinalityViolation:
        assert True
    else:
        assert False

    try:
        m.car.single()
    except CardinalityViolation:
        assert True
    else:
        assert False

    c = Car(version=2).save()
    m.car.relate(c)
    assert m.car.single().version == 2

    try:
        m.car.unrelate(c)
    except AttemptedCardinalityViolation:
        assert True
    else:
        assert False


def test_cardinality_one():
    Monkey.relate('toothbrush', ('HAS_TOOTHBRUSH', OUTGOING), to=ToothBrush, cardinality=One)
    m = Monkey(name='jerry').save()

    try:
        m.toothbrush.all()
    except CardinalityViolation:
        assert True
    else:
        assert False

    try:
        m.toothbrush.single()
    except CardinalityViolation:
        assert True
    else:
        assert False

    b = ToothBrush(name='Jim').save()
    m.toothbrush.relate(b)
    assert m.toothbrush.single().name == 'Jim'

    x = ToothBrush(name='Jim').save
    try:
        m.toothbrush.relate(x)
    except AttemptedCardinalityViolation:
        assert True
    else:
        assert False

    try:
        m.toothbrush.unrelate(b)
    except AttemptedCardinalityViolation:
        assert True
    else:
        assert False
