from pytest import raises

from neomodel import (
    AttemptedCardinalityViolation,
    CardinalityViolation,
    IntegerProperty,
    One,
    OneOrMore,
    RelationshipTo,
    StringProperty,
    StructuredNode,
    ZeroOrMore,
    ZeroOrOne,
    db,
)


class HairDryer(StructuredNode):
    version = IntegerProperty()


class ScrewDriver(StructuredNode):
    version = IntegerProperty()


class Car(StructuredNode):
    version = IntegerProperty()


class Monkey(StructuredNode):
    name = StringProperty()
    dryers = RelationshipTo("HairDryer", "OWNS_DRYER", cardinality=ZeroOrMore)
    driver = RelationshipTo("ScrewDriver", "HAS_SCREWDRIVER", cardinality=ZeroOrOne)
    car = RelationshipTo("Car", "HAS_CAR", cardinality=OneOrMore)
    toothbrush = RelationshipTo("ToothBrush", "HAS_TOOTHBRUSH", cardinality=One)


class ToothBrush(StructuredNode):
    name = StringProperty()


def test_cardinality_zero_or_more():
    m = Monkey(name="tim").save()
    assert m.dryers.all() == []
    assert m.dryers.single() is None
    h = HairDryer(version=1).save()

    m.dryers.connect(h)
    assert len(m.dryers.all()) == 1
    assert m.dryers.single().version == 1

    m.dryers.disconnect(h)
    assert m.dryers.all() == []
    assert m.dryers.single() is None

    h2 = HairDryer(version=2).save()
    m.dryers.connect(h)
    m.dryers.connect(h2)
    m.dryers.disconnect_all()
    assert m.dryers.all() == []
    assert m.dryers.single() is None


def test_cardinality_zero_or_one():
    m = Monkey(name="bob").save()
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

    # Forcing creation of a second ToothBrush to go around
    # AttemptedCardinalityViolation
    db.cypher_query(
        """
        MATCH (m:Monkey WHERE m.name="bob")
        CREATE (s:ScrewDriver {version:3})
        WITH m, s
        CREATE (m)-[:HAS_SCREWDRIVER]->(s)
    """
    )
    with raises(
        CardinalityViolation, match=r"CardinalityViolation: Expected: .*, got: 2."
    ):
        m.driver.all()


def test_cardinality_one_or_more():
    m = Monkey(name="jerry").save()

    with raises(CardinalityViolation):
        m.car.all()

    with raises(CardinalityViolation):
        m.car.single()

    c = Car(version=2).save()
    m.car.connect(c)
    assert m.car.single().version == 2

    cars = m.car.all()
    assert len(cars) == 1

    with raises(AttemptedCardinalityViolation):
        m.car.disconnect(c)

    d = Car(version=3).save()
    m.car.connect(d)
    cars = m.car.all()
    assert len(cars) == 2

    m.car.disconnect(d)
    cars = m.car.all()
    assert len(cars) == 1


def test_cardinality_one():
    m = Monkey(name="jerry").save()

    with raises(
        CardinalityViolation, match=r"CardinalityViolation: Expected: .*, got: none."
    ):
        m.toothbrush.all()

    with raises(CardinalityViolation):
        m.toothbrush.single()

    b = ToothBrush(name="Jim").save()
    m.toothbrush.connect(b)
    assert m.toothbrush.single().name == "Jim"

    x = ToothBrush(name="Jim").save
    with raises(AttemptedCardinalityViolation):
        m.toothbrush.connect(x)

    with raises(AttemptedCardinalityViolation):
        m.toothbrush.disconnect(b)

    with raises(AttemptedCardinalityViolation):
        m.toothbrush.disconnect_all()

    # Forcing creation of a second ToothBrush to go around
    # AttemptedCardinalityViolation
    db.cypher_query(
        """
        MATCH (m:Monkey WHERE m.name="jerry")
        CREATE (t:ToothBrush {name:"Jim"})
        WITH m, t
        CREATE (m)-[:HAS_TOOTHBRUSH]->(t)
    """
    )
    with raises(
        CardinalityViolation, match=r"CardinalityViolation: Expected: .*, got: 2."
    ):
        m.toothbrush.all()

    jp = Monkey(name="Jean-Pierre")
    with raises(ValueError, match="Node has not been saved cannot connect!"):
        jp.toothbrush.connect(b)
