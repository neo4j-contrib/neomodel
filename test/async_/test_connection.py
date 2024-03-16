import os
from test._async_compat import mark_async_test
from test.conftest import NEO4J_PASSWORD, NEO4J_URL, NEO4J_USERNAME

import pytest
from neo4j import AsyncDriver, AsyncGraphDatabase
from neo4j.debug import watch

from neomodel import AsyncStructuredNode, StringProperty, adb, config


@mark_async_test
@pytest.fixture(autouse=True)
async def setup_teardown():
    yield
    # Teardown actions after tests have run
    # Reconnect to initial URL for potential subsequent tests
    await adb.close_connection()
    await adb.set_connection(url=config.DATABASE_URL)


@pytest.fixture(autouse=True, scope="session")
def neo4j_logging():
    with watch("neo4j"):
        yield


@mark_async_test
async def get_current_database_name() -> str:
    """
    Fetches the name of the currently active database from the Neo4j database.

    Returns:
    - str: The name of the current database.
    """
    results, meta = await adb.cypher_query("CALL db.info")
    results_as_dict = [dict(zip(meta, row)) for row in results]

    return results_as_dict[0]["name"]


class Pastry(AsyncStructuredNode):
    name = StringProperty(unique_index=True)


@mark_async_test
async def test_set_connection_driver_works():
    # Verify that current connection is up
    assert await Pastry(name="Chocolatine").save()
    await adb.close_connection()

    # Test connection using a driver
    await adb.set_connection(
        driver=AsyncGraphDatabase().driver(
            NEO4J_URL, auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
        )
    )
    assert await Pastry(name="Croissant").save()


@mark_async_test
async def test_config_driver_works():
    # Verify that current connection is up
    assert await Pastry(name="Chausson aux pommes").save()
    await adb.close_connection()

    # Test connection using a driver defined in config
    driver: AsyncDriver = AsyncGraphDatabase().driver(
        NEO4J_URL, auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
    )

    config.DRIVER = driver
    assert await Pastry(name="Grignette").save()

    # Clear config
    # No need to close connection - pytest teardown will do it
    config.DRIVER = None


@mark_async_test
async def test_connect_to_non_default_database():
    if not await adb.edition_is_enterprise():
        pytest.skip("Skipping test for community edition - no multi database in CE")
    database_name = "pastries"
    await adb.cypher_query(f"CREATE DATABASE {database_name} IF NOT EXISTS")
    await adb.close_connection()

    # Set database name in url - for url init only
    await adb.set_connection(url=f"{config.DATABASE_URL}/{database_name}")
    assert await get_current_database_name() == "pastries"

    await adb.close_connection()

    # Set database name in config - for both url and driver init
    config.DATABASE_NAME = database_name

    # url init
    await adb.set_connection(url=config.DATABASE_URL)
    assert await get_current_database_name() == "pastries"

    await adb.close_connection()

    # driver init
    await adb.set_connection(
        driver=AsyncGraphDatabase().driver(
            NEO4J_URL, auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
        )
    )
    assert await get_current_database_name() == "pastries"

    # Clear config
    # No need to close connection - pytest teardown will do it
    config.DATABASE_NAME = None


@mark_async_test
@pytest.mark.parametrize(
    "url", ["bolt://user:password", "http://user:password@localhost:7687"]
)
async def test_wrong_url_format(url):
    with pytest.raises(
        ValueError,
        match=rf"Expecting url format: bolt://user:password@localhost:7687 got {url}",
    ):
        await adb.set_connection(url=url)


@mark_async_test
@pytest.mark.parametrize("protocol", ["neo4j+s", "neo4j+ssc", "bolt+s", "bolt+ssc"])
async def test_connect_to_aura(protocol):
    cypher_return = "hello world"
    default_cypher_query = f"RETURN '{cypher_return}'"
    await adb.close_connection()

    await _set_connection(protocol=protocol)
    result, _ = await adb.cypher_query(default_cypher_query)

    assert len(result) > 0
    assert result[0][0] == cypher_return


async def _set_connection(protocol):
    AURA_TEST_DB_USER = os.environ["AURA_TEST_DB_USER"]
    AURA_TEST_DB_PASSWORD = os.environ["AURA_TEST_DB_PASSWORD"]
    AURA_TEST_DB_HOSTNAME = os.environ["AURA_TEST_DB_HOSTNAME"]

    database_url = f"{protocol}://{AURA_TEST_DB_USER}:{AURA_TEST_DB_PASSWORD}@{AURA_TEST_DB_HOSTNAME}"
    await adb.set_connection(url=database_url)
