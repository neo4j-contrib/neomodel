import io
from test._async_compat import mark_async_test
from unittest.mock import patch

from pytest import raises

from neomodel import (
    AsyncOne,
    AsyncOneOrMore,
    AsyncRelationshipFrom,
    AsyncRelationshipTo,
    AsyncStructuredNode,
    AsyncZeroOrMore,
    AsyncZeroOrOne,
    AttemptedCardinalityViolation,
    CardinalityViolation,
    IntegerProperty,
    StringProperty,
    adb,
    get_config,
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


class Owner(AsyncStructuredNode):
    name = StringProperty(required=True)
    pets = AsyncRelationshipTo("Pet", "OWNS")


class Pet(AsyncStructuredNode):
    name = StringProperty(required=True)
    owner = AsyncRelationshipFrom("Owner", "OWNS", cardinality=AsyncOne)


class Company(AsyncStructuredNode):
    name = StringProperty(required=True)
    employees = AsyncRelationshipTo("Employee", "EMPLOYS")


class Employee(AsyncStructuredNode):
    name = StringProperty(required=True)
    employer = AsyncRelationshipFrom("Company", "EMPLOYS", cardinality=AsyncZeroOrOne)
    offices = AsyncRelationshipFrom("Office", "HOSTS", cardinality=AsyncOneOrMore)


class Office(AsyncStructuredNode):
    name = StringProperty(required=True)


class Manager(AsyncStructuredNode):
    name = StringProperty(required=True)
    assistant = AsyncRelationshipTo("Assistant", "MANAGES", cardinality=AsyncOne)


class Assistant(AsyncStructuredNode):
    name = StringProperty(required=True)
    boss = AsyncRelationshipFrom("Manager", "MANAGES", cardinality=AsyncOne)


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
    with raises(AttemptedCardinalityViolation) as exc_info:
        await m.driver.connect(j)

    error_message = str(exc_info.value)
    assert (
        f"Node already has zero or one relationship in a outgoing direction of type HAS_SCREWDRIVER on node ({m.element_id}) of class 'Monkey'. Use reconnect() to replace the existing relationship."
        == error_message
    )

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

    with raises(AttemptedCardinalityViolation) as exc_info:
        await m.car.disconnect(c)

    error_message = str(exc_info.value)
    assert "One or more expected" == error_message

    d = await Car(version=3).save()
    await m.car.connect(d)
    cars = await m.car.all()
    assert len(cars) == 2

    await m.car.disconnect(d)
    cars = await m.car.all()
    assert len(cars) == 1

    with raises(AttemptedCardinalityViolation):
        await m.car.disconnect_all()

    assert await m.car.single() is not None


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
    with raises(AttemptedCardinalityViolation) as exc_info:
        await m.toothbrush.connect(x)

    error_message = str(exc_info.value)
    assert (
        f"Node already has one relationship in a outgoing direction of type HAS_TOOTHBRUSH on node ({m.element_id}) of class 'Monkey'. Use reconnect() to replace the existing relationship."
        == error_message
    )

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


@mark_async_test
async def test_relationship_from_one_cardinality_enforced():
    """
    Test that RelationshipFrom with cardinality=One prevents multiple connections.

    This addresses the GitHub issue where RelationshipFrom cardinality constraints
    were not being enforced.
    """
    # Setup
    config = get_config()
    config.soft_cardinality_check = False
    owner1 = await Owner(name="Alice").save()
    owner2 = await Owner(name="Bob").save()
    pet = await Pet(name="Fluffy").save()

    # First connection should succeed
    await owner1.pets.connect(pet)

    # Verify connection was established
    assert await pet.owner.single() == owner1
    assert pet in await owner1.pets.all()

    # Second connection should fail due to RelationshipFrom cardinality=One
    with raises(AttemptedCardinalityViolation):
        await owner2.pets.connect(pet)

    stream = io.StringIO()
    with patch("sys.stdout", new=stream):
        config.soft_cardinality_check = True
        await owner2.pets.connect(pet)
        assert pet in await owner2.pets.all()

    console_output = stream.getvalue()
    assert "Cardinality violation detected" in console_output
    assert "Soft check is enabled so the relationship will be created" in console_output

    config.soft_cardinality_check = False


@mark_async_test
async def test_relationship_from_zero_or_one_cardinality_enforced():
    """
    Test that RelationshipFrom with cardinality=ZeroOrOne prevents multiple connections.
    """
    # Setup
    config = get_config()
    config.soft_cardinality_check = False
    company1 = await Company(name="TechCorp").save()
    company2 = await Company(name="StartupInc").save()
    employee = await Employee(name="John").save()

    # First connection should succeed
    await company1.employees.connect(employee)

    # Verify connection was established
    assert await employee.employer.single() == company1
    assert employee in await company1.employees.all()

    # Second connection should fail due to RelationshipFrom cardinality=ZeroOrOne
    with raises(AttemptedCardinalityViolation):
        await company2.employees.connect(employee)

    stream = io.StringIO()
    with patch("sys.stdout", new=stream):
        config.soft_cardinality_check = True
        await company2.employees.connect(employee)
        assert employee in await company2.employees.all()

    console_output = stream.getvalue()
    assert "Cardinality violation detected" in console_output
    assert "Soft check is enabled so the relationship will be created" in console_output

    config.soft_cardinality_check = False


@mark_async_test
async def test_relationship_from_one_or_more_cardinality_enforced():
    """
    Test that RelationshipFrom with cardinality=OneOrMore prevents disconnecting all nodes.
    """
    # Setup
    config = get_config()
    config.soft_cardinality_check = False
    office = await Office(name="Headquarters").save()
    employee = await Employee(name="John").save()
    await employee.offices.connect(office)

    with raises(AttemptedCardinalityViolation):
        await employee.offices.disconnect(office)

    with raises(AttemptedCardinalityViolation):
        await employee.offices.disconnect_all()

    assert await employee.offices.single() is not None

    config.soft_cardinality_check = False


@mark_async_test
async def test_bidirectional_cardinality_validation():
    """
    Test that cardinality is validated on both ends when both sides have constraints.
    """
    # Setup
    config = get_config()
    config.soft_cardinality_check = False
    manager1 = await Manager(name="Sarah").save()
    manager2 = await Manager(name="David").save()
    assistant = await Assistant(name="Alex").save()

    # First connection should succeed
    await manager1.assistant.connect(assistant)

    # Verify bidirectional connection
    assert await manager1.assistant.single() == assistant
    assert await assistant.boss.single() == manager1

    # Second manager trying to connect to same assistant should fail
    with raises(AttemptedCardinalityViolation):
        await manager2.assistant.connect(assistant)

    stream = io.StringIO()
    with patch("sys.stdout", new=stream):
        config.soft_cardinality_check = True
        await manager2.assistant.connect(assistant)
        assert assistant in await manager2.assistant.all()

    console_output = stream.getvalue()
    assert "Cardinality violation detected" in console_output
    assert "Soft check is enabled so the relationship will be created" in console_output

    config.soft_cardinality_check = False
