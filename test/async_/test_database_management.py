import asyncio
from test._async_compat import mark_async_test

import neo4j
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
from neomodel._async_compat.util import AsyncUtil
from neomodel.async_.database import AsyncDatabase


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


@mark_async_test
async def test_adb_singleton_behavior():
    """Test that AsyncDatabase enforces singleton behavior."""

    # Get the module-level instance
    adb1 = AsyncDatabase.get_instance()

    # Try to create another instance directly
    adb2 = AsyncDatabase()

    # Try to create another instance via get_instance
    adb3 = AsyncDatabase.get_instance()

    # All instances should be the same object
    assert adb1 is adb2, "Direct instantiation should return the same instance"
    assert adb1 is adb3, "get_instance should return the same instance"
    assert adb2 is adb3, "All instances should be the same object"

    # Test that the module-level 'adb' is also the same instance
    assert adb is adb1, "Module-level 'adb' should be the same instance"


@mark_async_test
async def test_async_database_properties():
    # A fresh instance of AsyncDatabase is not yet connected
    await AsyncDatabase.reset_instance()
    reset_singleton = AsyncDatabase.get_instance()
    assert reset_singleton._active_transaction is None
    assert reset_singleton.url is None
    assert reset_singleton.driver is None
    assert reset_singleton._session is None
    assert reset_singleton._pid is None
    assert reset_singleton._database_name is neo4j.DEFAULT_DATABASE
    assert reset_singleton._database_version is None
    assert reset_singleton._database_edition is None
    assert reset_singleton.impersonated_user is None
    assert reset_singleton._parallel_runtime is False


@mark_async_test
async def test_parallel_transactions():
    if not AsyncUtil.is_async_code:
        pytest.skip("Async only test")

    transactions = set()
    sessions = set()

    async def query(i: int):
        await asyncio.sleep(0.05)

        assert adb._active_transaction is None
        assert adb._session is None

        async with adb.transaction:
            # ensure transaction and session are unique for async context
            transaction_id = id(adb._active_transaction)
            assert transaction_id not in transactions
            transactions.add(transaction_id)

            session_id = id(adb._session)
            assert session_id not in sessions
            sessions.add(session_id)

            result, _ = await adb.cypher_query(
                "CALL apoc.util.sleep($delay_ms) RETURN $task_id as task_id, $delay_ms as slept",
                {"delay_ms": i * 505, "task_id": i},
            )

        return result[0][0], result[0][1], transaction_id, session_id

    _ = await asyncio.gather(*(query(i) for i in range(1, 5)))
