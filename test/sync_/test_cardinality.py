import io
from test._async_compat import mark_sync_test
from unittest.mock import patch

from pytest import raises

from neomodel import (
    AttemptedCardinalityViolation,
    CardinalityViolation,
    IntegerProperty,
    One,
    OneOrMore,
    RelationshipFrom,
    RelationshipTo,
    StringProperty,
    StructuredNode,
    ZeroOrMore,
    ZeroOrOne,
    config,
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


class Owner(StructuredNode):
    name = StringProperty(required=True)
    pets = RelationshipTo("Pet", "OWNS")


class Pet(StructuredNode):
    name = StringProperty(required=True)
    owner = RelationshipFrom("Owner", "OWNS", cardinality=One)


class Company(StructuredNode):
    name = StringProperty(required=True)
    employees = RelationshipTo("Employee", "EMPLOYS")


class Employee(StructuredNode):
    name = StringProperty(required=True)
    employer = RelationshipFrom("Company", "EMPLOYS", cardinality=ZeroOrOne)


class Manager(StructuredNode):
    name = StringProperty(required=True)
    assistant = RelationshipTo("Assistant", "MANAGES", cardinality=One)


class Assistant(StructuredNode):
    name = StringProperty(required=True)
    boss = RelationshipFrom("Manager", "MANAGES", cardinality=One)


@mark_sync_test
def test_cardinality_zero_or_more():
    m = Monkey(name="tim").save()
    assert m.dryers.all() == []
    single_dryer = m.driver.single()
    assert single_dryer is None
    h = HairDryer(version=1).save()

    m.dryers.connect(h)
    assert len(m.dryers.all()) == 1
    single_dryer = m.dryers.single()
    assert single_dryer.version == 1

    m.dryers.disconnect(h)
    assert m.dryers.all() == []
    single_dryer = m.driver.single()
    assert single_dryer is None

    h2 = HairDryer(version=2).save()
    m.dryers.connect(h)
    m.dryers.connect(h2)
    m.dryers.disconnect_all()
    assert m.dryers.all() == []
    single_dryer = m.driver.single()
    assert single_dryer is None


@mark_sync_test
def test_cardinality_zero_or_one():
    m = Monkey(name="bob").save()
    assert m.driver.all() == []
    single_driver = m.driver.single()
    assert m.driver.single() is None
    h = ScrewDriver(version=1).save()

    m.driver.connect(h)
    assert len(m.driver.all()) == 1
    single_driver = m.driver.single()
    assert single_driver.version == 1

    j = ScrewDriver(version=2).save()
    with raises(AttemptedCardinalityViolation):
        m.driver.connect(j)

    m.driver.reconnect(h, j)
    single_driver = m.driver.single()
    assert single_driver.version == 2

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


@mark_sync_test
def test_cardinality_one_or_more():
    m = Monkey(name="jerry").save()

    with raises(CardinalityViolation):
        m.car.all()

    with raises(CardinalityViolation):
        m.car.single()

    c = Car(version=2).save()
    m.car.connect(c)
    single_car = m.car.single()
    assert single_car.version == 2

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


@mark_sync_test
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
    single_toothbrush = m.toothbrush.single()
    assert single_toothbrush.name == "Jim"

    x = ToothBrush(name="Jim").save()
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


@mark_sync_test
def test_relationship_from_one_cardinality_enforced():
    """
    Test that RelationshipFrom with cardinality=One prevents multiple connections.

    This addresses the GitHub issue where RelationshipFrom cardinality constraints
    were not being enforced.
    """
    # Setup
    config.SOFT_INVERSE_CARDINALITY_CHECK = False
    owner1 = Owner(name="Alice").save()
    owner2 = Owner(name="Bob").save()
    pet = Pet(name="Fluffy").save()

    # First connection should succeed
    owner1.pets.connect(pet)

    # Verify connection was established
    assert pet.owner.single() == owner1
    assert pet in owner1.pets.all()

    # Second connection should fail due to RelationshipFrom cardinality=One
    with raises(AttemptedCardinalityViolation):
        owner2.pets.connect(pet)

    stream = io.StringIO()
    with patch("sys.stdout", new=stream):
        config.SOFT_INVERSE_CARDINALITY_CHECK = True
        owner2.pets.connect(pet)
        assert pet in owner2.pets.all()

    console_output = stream.getvalue()
    assert "Cardinality violation detected" in console_output
    assert "Soft check is enabled so the relationship will be created" in console_output
    assert "strict check will be enabled by default in version 6.0" in console_output


@mark_sync_test
def test_relationship_from_zero_or_one_cardinality_enforced():
    """
    Test that RelationshipFrom with cardinality=ZeroOrOne prevents multiple connections.
    """
    # Setup
    config.SOFT_INVERSE_CARDINALITY_CHECK = False
    company1 = Company(name="TechCorp").save()
    company2 = Company(name="StartupInc").save()
    employee = Employee(name="John").save()

    # First connection should succeed
    company1.employees.connect(employee)

    # Verify connection was established
    assert employee.employer.single() == company1
    assert employee in company1.employees.all()

    # Second connection should fail due to RelationshipFrom cardinality=ZeroOrOne
    with raises(AttemptedCardinalityViolation):
        company2.employees.connect(employee)

    stream = io.StringIO()
    with patch("sys.stdout", new=stream):
        config.SOFT_INVERSE_CARDINALITY_CHECK = True
        company2.employees.connect(employee)
        assert employee in company2.employees.all()

    console_output = stream.getvalue()
    assert "Cardinality violation detected" in console_output
    assert "Soft check is enabled so the relationship will be created" in console_output
    assert "strict check will be enabled by default in version 6.0" in console_output


@mark_sync_test
def test_bidirectional_cardinality_validation():
    """
    Test that cardinality is validated on both ends when both sides have constraints.
    """
    # Setup
    config.SOFT_INVERSE_CARDINALITY_CHECK = False
    manager1 = Manager(name="Sarah").save()
    manager2 = Manager(name="David").save()
    assistant = Assistant(name="Alex").save()

    # First connection should succeed
    manager1.assistant.connect(assistant)

    # Verify bidirectional connection
    assert manager1.assistant.single() == assistant
    assert assistant.boss.single() == manager1

    # Second manager trying to connect to same assistant should fail
    with raises(AttemptedCardinalityViolation):
        manager2.assistant.connect(assistant)

    stream = io.StringIO()
    with patch("sys.stdout", new=stream):
        config.SOFT_INVERSE_CARDINALITY_CHECK = True
        manager2.assistant.connect(assistant)
        assert assistant in manager2.assistant.all()

    console_output = stream.getvalue()
    assert "Cardinality violation detected" in console_output
    assert "Soft check is enabled so the relationship will be created" in console_output
    assert "strict check will be enabled by default in version 6.0" in console_output
