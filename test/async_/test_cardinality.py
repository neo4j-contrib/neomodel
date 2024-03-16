from test._async_compat import mark_async_test

from pytest import raises

from neomodel import (
    AsyncOne,
    AsyncOneOrMore,
    AsyncRelationshipTo,
    AsyncStructuredNode,
    AsyncZeroOrMore,
    AsyncZeroOrOne,
    AttemptedCardinalityViolation,
    CardinalityViolation,
    IntegerProperty,
    StringProperty,
    adb,
)


class HairDryer(AsyncStructuredNode):
    version = IntegerProperty()


class ScrewDriver(AsyncStructuredNode):
    version = IntegerProperty()


class Car(AsyncStructuredNode):
    version = IntegerProperty()


class Monkey(AsyncStructuredNode):
    name = StringProperty()
    dryers = AsyncRelationshipTo("HairDryer", "OWNS_DRYER", cardinality=AsyncZeroOrMore)
    driver = AsyncRelationshipTo(
        "ScrewDriver", "HAS_SCREWDRIVER", cardinality=AsyncZeroOrOne
    )
    car = AsyncRelationshipTo("Car", "HAS_CAR", cardinality=AsyncOneOrMore)
    toothbrush = AsyncRelationshipTo(
        "ToothBrush", "HAS_TOOTHBRUSH", cardinality=AsyncOne
    )


class ToothBrush(AsyncStructuredNode):
    name = StringProperty()


@mark_async_test
async def test_cardinality_zero_or_more():
    m = await Monkey(name="tim").save()
    assert await m.dryers.all() == []
    single_dryer = await m.driver.single()
    assert single_dryer is None
    h = await HairDryer(version=1).save()

    await m.dryers.connect(h)
    assert len(await m.dryers.all()) == 1
    single_dryer = await m.dryers.single()
    assert single_dryer.version == 1

    await m.dryers.disconnect(h)
    assert await m.dryers.all() == []
    single_dryer = await m.driver.single()
    assert single_dryer is None

    h2 = await HairDryer(version=2).save()
    await m.dryers.connect(h)
    await m.dryers.connect(h2)
    await m.dryers.disconnect_all()
    assert await m.dryers.all() == []
    single_dryer = await m.driver.single()
    assert single_dryer is None


@mark_async_test
async def test_cardinality_zero_or_one():
    m = await Monkey(name="bob").save()
    assert await m.driver.all() == []
    single_driver = await m.driver.single()
    assert await m.driver.single() is None
    h = await ScrewDriver(version=1).save()

    await m.driver.connect(h)
    assert len(await m.driver.all()) == 1
    single_driver = await m.driver.single()
    assert single_driver.version == 1

    j = await ScrewDriver(version=2).save()
    with raises(AttemptedCardinalityViolation):
        await m.driver.connect(j)

    await m.driver.reconnect(h, j)
    single_driver = await m.driver.single()
    assert single_driver.version == 2

    # Forcing creation of a second ToothBrush to go around
    # AttemptedCardinalityViolation
    await adb.cypher_query(
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
        await m.driver.all()


@mark_async_test
async def test_cardinality_one_or_more():
    m = await Monkey(name="jerry").save()

    with raises(CardinalityViolation):
        await m.car.all()

    with raises(CardinalityViolation):
        await m.car.single()

    c = await Car(version=2).save()
    await m.car.connect(c)
    single_car = await m.car.single()
    assert single_car.version == 2

    cars = await m.car.all()
    assert len(cars) == 1

    with raises(AttemptedCardinalityViolation):
        await m.car.disconnect(c)

    d = await Car(version=3).save()
    await m.car.connect(d)
    cars = await m.car.all()
    assert len(cars) == 2

    await m.car.disconnect(d)
    cars = await m.car.all()
    assert len(cars) == 1


@mark_async_test
async def test_cardinality_one():
    m = await Monkey(name="jerry").save()

    with raises(
        CardinalityViolation, match=r"CardinalityViolation: Expected: .*, got: none."
    ):
        await m.toothbrush.all()

    with raises(CardinalityViolation):
        await m.toothbrush.single()

    b = await ToothBrush(name="Jim").save()
    await m.toothbrush.connect(b)
    single_toothbrush = await m.toothbrush.single()
    assert single_toothbrush.name == "Jim"

    x = await ToothBrush(name="Jim").save()
    with raises(AttemptedCardinalityViolation):
        await m.toothbrush.connect(x)

    with raises(AttemptedCardinalityViolation):
        await m.toothbrush.disconnect(b)

    with raises(AttemptedCardinalityViolation):
        await m.toothbrush.disconnect_all()

    # Forcing creation of a second ToothBrush to go around
    # AttemptedCardinalityViolation
    await adb.cypher_query(
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
        await m.toothbrush.all()

    jp = Monkey(name="Jean-Pierre")
    with raises(ValueError, match="Node has not been saved cannot connect!"):
        await jp.toothbrush.connect(b)
