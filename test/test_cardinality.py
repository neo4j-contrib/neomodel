from neomodel import (StructuredNode, StringProperty, IntegerProperty,
         AttemptedCardinalityViolation, CardinalityViolation,
         OneOrMore, ZeroOrMore, ZeroOrOne, One)
from neomodel.core import connection_adapter


class HairDryer(StructuredNode):
    version = IntegerProperty()


class ScrewDriver(StructuredNode):
    version = IntegerProperty()


class Car(StructuredNode):
    version = IntegerProperty()


class Monkey(StructuredNode):
    name = StringProperty()


class ToothBrush(StructuredNode):
    name = StringProperty()


def setup():
    connection_adapter().client.clear()


def test_cardinality_zero_or_more():
    Monkey.outgoing('OWNS_DRYER', 'dryers', to=HairDryer, cardinality=ZeroOrMore)

    m = Monkey(name='tim').save()
    assert m.dryers.all() == []
    assert m.dryers.single() == None
    h = HairDryer(version=1).save()

    m.dryers.connect(h)
    assert len(m.dryers.all()) == 1
    assert m.dryers.single().version == 1

    m.dryers.disconnect(h)
    assert m.dryers.all() == []
    assert m.dryers.single() == None


def test_cardinality_zero_or_one():
    Monkey.outgoing('HAS_SCREWDRIVER', 'driver', to=ScrewDriver, cardinality=ZeroOrOne)

    m = Monkey(name='bob').save()
    assert m.driver.all() == []
    assert m.driver.single() == None
    h = ScrewDriver(version=1).save()

    m.driver.connect(h)
    assert len(m.driver.all()) == 1
    assert m.driver.single().version == 1

    j = ScrewDriver(version=2).save()
    try:
        m.driver.connect(j)
    except AttemptedCardinalityViolation:
        assert True
    else:
        assert False

    m.driver.reconnect(h, j)
    assert m.driver.single().version == 2


def test_cardinality_one_or_more():
    Monkey.outgoing('HAS_CAR', 'car', to=Car, cardinality=OneOrMore)
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
    m.car.connect(c)
    assert m.car.single().version == 2

    try:
        m.car.disconnect(c)
    except AttemptedCardinalityViolation:
        assert True
    else:
        assert False


def test_cardinality_one():
    Monkey.outgoing('HAS_TOOTHBRUSH', 'toothbrush', to=ToothBrush, cardinality=One)
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
    m.toothbrush.connect(b)
    assert m.toothbrush.single().name == 'Jim'

    x = ToothBrush(name='Jim').save
    try:
        m.toothbrush.connect(x)
    except AttemptedCardinalityViolation:
        assert True
    else:
        assert False

    try:
        m.toothbrush.disconnect(b)
    except AttemptedCardinalityViolation:
        assert True
    else:
        assert False
