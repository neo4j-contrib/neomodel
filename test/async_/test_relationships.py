from test._async_compat import mark_async_test

from pytest import raises

from neomodel import (
    AsyncMutuallyExclusive,
    AsyncOne,
    AsyncRelationship,
    AsyncRelationshipFrom,
    AsyncRelationshipTo,
    AsyncStructuredNode,
    AsyncStructuredRel,
    IntegerProperty,
    Q,
    StringProperty,
    adb,
)
from neomodel.exceptions import MutualExclusionViolation


class PersonWithRels(AsyncStructuredNode):
    name = StringProperty(unique_index=True)
    age = IntegerProperty(index=True)
    is_from = AsyncRelationshipTo("Country", "IS_FROM")
    knows = AsyncRelationship("PersonWithRels", "KNOWS")

    @property
    def special_name(self):
        return self.name

    def special_power(self):
        return "I have no powers"


class Country(AsyncStructuredNode):
    code = StringProperty(unique_index=True)
    inhabitant = AsyncRelationshipFrom(PersonWithRels, "IS_FROM")
    president = AsyncRelationshipTo(PersonWithRels, "PRESIDENT", cardinality=AsyncOne)


class SuperHero(PersonWithRels):
    power = StringProperty(index=True)

    def special_power(self):
        return "I have powers"


@mark_async_test
async def test_actions_on_deleted_node():
    u = await PersonWithRels(name="Jim2", age=3).save()
    await u.delete()
    with raises(ValueError):
        await u.is_from.connect(None)

    with raises(ValueError):
        await u.is_from.get()

    with raises(ValueError):
        await u.save()


@mark_async_test
async def test_bidirectional_relationships():
    u = await PersonWithRels(name="Jim", age=3).save()
    assert u

    de = await Country(code="DE").save()
    assert de

    assert not await u.is_from.all()

    assert u.is_from.__class__.__name__ == "AsyncZeroOrMore"
    await u.is_from.connect(de)

    assert len(await u.is_from.all()) == 1

    assert await u.is_from.is_connected(de)

    b = (await u.is_from.all())[0]
    assert b.__class__.__name__ == "Country"
    assert b.code == "DE"

    s = (await b.inhabitant.all())[0]
    assert s.name == "Jim"

    await u.is_from.disconnect(b)
    assert not await u.is_from.is_connected(b)


@mark_async_test
async def test_either_direction_connect():
    rey = await PersonWithRels(name="Rey", age=3).save()
    sakis = await PersonWithRels(name="Sakis", age=3).save()

    await rey.knows.connect(sakis)
    assert await rey.knows.is_connected(sakis)
    assert await sakis.knows.is_connected(rey)
    await sakis.knows.connect(rey)

    result, _ = await sakis.cypher(
        f"""MATCH (us), (them)
            WHERE {await adb.get_id_method()}(us)=$self and {await adb.get_id_method()}(them)=$them
            MATCH (us)-[r:KNOWS]-(them) RETURN COUNT(r)""",
        {"them": await adb.parse_element_id(rey.element_id)},
    )
    assert int(result[0][0]) == 1

    rel = await rey.knows.relationship(sakis)
    assert isinstance(rel, AsyncStructuredRel)

    rels = await rey.knows.all_relationships(sakis)
    assert isinstance(rels[0], AsyncStructuredRel)


@mark_async_test
async def test_search_and_filter_and_exclude():
    fred = await PersonWithRels(name="Fred", age=13).save()
    zz = await Country(code="ZZ").save()
    zx = await Country(code="ZX").save()
    zt = await Country(code="ZY").save()
    await fred.is_from.connect(zz)
    await fred.is_from.connect(zx)
    await fred.is_from.connect(zt)
    result = await fred.is_from.filter(code="ZX")
    assert result[0].code == "ZX"

    result = await fred.is_from.filter(code="ZY")
    assert result[0].code == "ZY"

    result = await fred.is_from.exclude(code="ZZ").exclude(code="ZY")
    assert result[0].code == "ZX" and len(result) == 1

    result = await fred.is_from.exclude(Q(code__contains="Y"))
    assert len(result) == 2

    result = await fred.is_from.filter(Q(code__contains="Z"))
    assert len(result) == 3


@mark_async_test
async def test_custom_methods():
    u = await PersonWithRels(name="Joe90", age=13).save()
    assert u.special_power() == "I have no powers"
    u = await SuperHero(name="Joe91", age=13, power="xxx").save()
    assert u.special_power() == "I have powers"
    assert u.special_name == "Joe91"


@mark_async_test
async def test_valid_reconnection():
    p = await PersonWithRels(name="ElPresidente", age=93).save()
    assert p

    pp = await PersonWithRels(name="TheAdversary", age=33).save()
    assert pp

    c = await Country(code="CU").save()
    assert c

    await c.president.connect(p)
    assert await c.president.is_connected(p)

    # the coup d'etat
    await c.president.reconnect(p, pp)
    assert await c.president.is_connected(pp)

    # reelection time
    await c.president.reconnect(pp, pp)
    assert await c.president.is_connected(pp)


@mark_async_test
async def test_valid_replace():
    brady = await PersonWithRels(name="Tom Brady", age=40).save()
    assert brady

    gronk = await PersonWithRels(name="Rob Gronkowski", age=28).save()
    assert gronk

    colbert = await PersonWithRels(name="Stephen Colbert", age=53).save()
    assert colbert

    hanks = await PersonWithRels(name="Tom Hanks", age=61).save()
    assert hanks

    await brady.knows.connect(gronk)
    await brady.knows.connect(colbert)
    assert len(await brady.knows.all()) == 2
    assert await brady.knows.is_connected(gronk)
    assert await brady.knows.is_connected(colbert)

    await brady.knows.replace(hanks)
    assert len(await brady.knows.all()) == 1
    assert await brady.knows.is_connected(hanks)
    assert not await brady.knows.is_connected(gronk)
    assert not await brady.knows.is_connected(colbert)


@mark_async_test
async def test_props_relationship():
    u = await PersonWithRels(name="Mar", age=20).save()
    assert u

    c = await Country(code="AT").save()
    assert c

    c2 = await Country(code="LA").save()
    assert c2

    with raises(NotImplementedError):
        await c.inhabitant.connect(u, properties={"city": "Thessaloniki"})


class JealousDog(AsyncStructuredNode):
    name = StringProperty(required=True)


class JealousCat(AsyncStructuredNode):
    name = StringProperty(required=True)


class ExclusivePerson(AsyncStructuredNode):
    name = StringProperty(required=True)

    # Define mutually exclusive relationships
    cat = AsyncRelationshipTo(
        "JealousCat",
        "HAS_PET",
        cardinality=AsyncMutuallyExclusive,
        exclusion_group=["dog"],
    )
    dog = AsyncRelationshipTo(
        "JealousDog",
        "HAS_PET",
        cardinality=AsyncMutuallyExclusive,
        exclusion_group=["cat"],
    )


class WeirdCompany(AsyncStructuredNode):
    name = StringProperty(required=True)

    # A company can have either full-time or part-time employees, but not both
    full_time_employees = AsyncRelationshipFrom(
        "WeirdEmployee",
        "WORKS_FULL_TIME_AT",
        cardinality=AsyncMutuallyExclusive,
        exclusion_group=["part_time_employees"],
    )
    part_time_employees = AsyncRelationshipFrom(
        "WeirdEmployee",
        "WORKS_PART_TIME_AT",
        cardinality=AsyncMutuallyExclusive,
        exclusion_group=["full_time_employees"],
    )


class WeirdEmployee(AsyncStructuredNode):
    name = StringProperty(required=True)
    salary = IntegerProperty()


class SingleMindedPerson(AsyncStructuredNode):
    name = StringProperty(required=True)

    # A person can be either friends or enemies with another person, but not both
    friends = AsyncRelationship(
        "SingleMindedPerson",
        "FRIENDS_WITH",
        cardinality=AsyncMutuallyExclusive,
        exclusion_group=["enemies"],
    )
    enemies = AsyncRelationship(
        "SingleMindedPerson",
        "ENEMIES_WITH",
        cardinality=AsyncMutuallyExclusive,
        exclusion_group=["friends"],
    )


@mark_async_test
async def test_mutually_exclusive_to_relationships():
    """Test RelationshipTo with MutuallyExclusive cardinality."""
    # Create test nodes
    bob = await ExclusivePerson(name="Bob").save()
    rex = await JealousDog(name="Rex").save()
    whiskers = await JealousCat(name="Whiskers").save()

    # Bob can have a dog
    await bob.dog.connect(rex)

    # But now Bob can't have a cat because he already has a dog
    with raises(MutualExclusionViolation):
        await bob.cat.connect(whiskers)

    # Create another person
    alice = await ExclusivePerson(name="Alice").save()

    # Alice can have a cat
    await alice.cat.connect(whiskers)

    # But now Alice can't have a dog because she already has a cat
    with raises(MutualExclusionViolation):
        await alice.dog.connect(rex)

    # If Alice disconnects her cat, she can then have a dog
    await alice.cat.disconnect(whiskers)
    await alice.dog.connect(rex)

    # Verify the connections
    assert len(await bob.dog.all()) == 1
    assert len(await bob.cat.all()) == 0
    assert len(await alice.dog.all()) == 1
    assert len(await alice.cat.all()) == 0


@mark_async_test
async def test_mutually_exclusive_from_relationships():
    """Test RelationshipFrom with MutuallyExclusive cardinality."""
    # Create test nodes
    tech_corp = await WeirdCompany(name="TechCorp").save()
    alice = await WeirdEmployee(name="Alice", salary=50000).save()
    bob = await WeirdEmployee(name="Bob", salary=30000).save()

    # TechCorp can have full-time employees
    await tech_corp.full_time_employees.connect(alice)

    # But now TechCorp can't have part-time employees
    with raises(MutualExclusionViolation):
        await tech_corp.part_time_employees.connect(bob)

    # Create another company
    retail_corp = await WeirdCompany(name="RetailCorp").save()

    # RetailCorp can have part-time employees
    await retail_corp.part_time_employees.connect(bob)

    # But now RetailCorp can't have full-time employees
    with raises(MutualExclusionViolation):
        await retail_corp.full_time_employees.connect(alice)

    # If RetailCorp disconnects its part-time employees, it can have full-time employees
    await retail_corp.part_time_employees.disconnect(bob)
    await retail_corp.full_time_employees.connect(alice)

    # Verify the connections
    assert len(await tech_corp.full_time_employees.all()) == 1
    assert len(await tech_corp.part_time_employees.all()) == 0
    assert len(await retail_corp.full_time_employees.all()) == 1
    assert len(await retail_corp.part_time_employees.all()) == 0


@mark_async_test
async def test_mutually_exclusive_bidirectional_relationships():
    """Test Relationship with MutuallyExclusive cardinality."""
    # Create test nodes
    alice = await SingleMindedPerson(name="Alice").save()
    bob = await SingleMindedPerson(name="Bob").save()
    charlie = await SingleMindedPerson(name="Charlie").save()

    # Alice and Bob can be friends
    await alice.friends.connect(bob)

    # But now Alice and Charlie can't be enemies
    with raises(MutualExclusionViolation):
        await alice.enemies.connect(charlie)

    # If Alice disconnects from being friends with Bob, she can be enemies with Charlie
    await alice.friends.disconnect(bob)
    await alice.enemies.connect(charlie)

    # Verify the connections
    assert len(await alice.friends.all()) == 0
    assert len(await alice.enemies.all()) == 1  # Charlie
    assert len(await charlie.friends.all()) == 0
    assert len(await charlie.enemies.all()) == 1  # Alice
    assert len(await bob.friends.all()) == 0
    assert len(await bob.enemies.all()) == 0
