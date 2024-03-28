from test._async_compat import mark_async_test

import pytest
from neo4j.exceptions import AuthError

from neomodel import (
    AsyncRelationshipTo,
    AsyncStructuredNode,
    AsyncStructuredRel,
    IntegerProperty,
    StringProperty,
    adb,
)


class City(AsyncStructuredNode):
    name = StringProperty()


class InCity(AsyncStructuredRel):
    creation_year = IntegerProperty(index=True)


class Venue(AsyncStructuredNode):
    name = StringProperty(unique_index=True)
    creator = StringProperty(index=True)
    in_city = AsyncRelationshipTo(City, relation_type="IN", model=InCity)


@mark_async_test
async def test_clear_database():
    venue = await Venue(name="Royal Albert Hall", creator="Queen Victoria").save()
    city = await City(name="London").save()
    await venue.in_city.connect(city)

    # Clear only the data
    await adb.clear_neo4j_database()
    database_is_populated, _ = await adb.cypher_query(
        "MATCH (a) return count(a)>0 as database_is_populated"
    )

    assert database_is_populated[0][0] is False

    await adb.install_all_labels()
    indexes = await adb.list_indexes(exclude_token_lookup=True)
    constraints = await adb.list_constraints()
    assert len(indexes) > 0
    assert len(constraints) > 0

    # Clear constraints and indexes too
    await adb.clear_neo4j_database(clear_constraints=True, clear_indexes=True)

    indexes = await adb.list_indexes(exclude_token_lookup=True)
    constraints = await adb.list_constraints()
    assert len(indexes) == 0
    assert len(constraints) == 0


@mark_async_test
async def test_change_password():
    prev_password = "foobarbaz"
    new_password = "newpassword"
    prev_url = f"bolt://neo4j:{prev_password}@localhost:7687"
    new_url = f"bolt://neo4j:{new_password}@localhost:7687"

    await adb.change_neo4j_password("neo4j", new_password)
    await adb.close_connection()

    await adb.set_connection(url=new_url)
    await adb.close_connection()

    with pytest.raises(AuthError):
        await adb.set_connection(url=prev_url)

    await adb.close_connection()

    await adb.set_connection(url=new_url)
    await adb.change_neo4j_password("neo4j", prev_password)
    await adb.close_connection()

    await adb.set_connection(url=prev_url)
