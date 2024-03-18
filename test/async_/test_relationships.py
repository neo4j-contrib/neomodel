from test._async_compat import mark_async_test

from pytest import raises

from neomodel import (
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
