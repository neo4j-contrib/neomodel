import os
from test._async_compat import (
    mark_async_function_auto_fixture,
    mark_async_session_auto_fixture,
    mark_async_test,
)
from test.conftest import NEO4J_PASSWORD, NEO4J_URL, NEO4J_USERNAME

import pytest
from neo4j import AsyncDriver, AsyncGraphDatabase
from neo4j.debug import watch

from neomodel import AsyncStructuredNode, StringProperty, adb, get_config


@mark_async_function_auto_fixture
async def setup_teardown(request):
    yield
    # Teardown actions after tests have run
    # Reconnect to initial URL for potential subsequent tests
    # Skip reconnection for Aura tests except bolt+ssc parameter
    should_reconnect = True
    if (
        "test_connect_to_aura" in request.node.name
        and "bolt+ssc" not in request.node.name
    ):
        should_reconnect = False

    if should_reconnect:
        await adb.close_connection()
        await adb.set_connection(url=get_config().database_url)


@mark_async_session_auto_fixture
async def neo4j_logging():
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

    config = get_config()
    config.driver = driver
    assert await Pastry(name="Grignette").save()

    # Clear config
    # No need to close connection - pytest teardown will do it
    config.driver = None


@mark_async_test
async def test_connect_to_non_default_database():
    if not await adb.edition_is_enterprise():
        pytest.skip("Skipping test for community edition - no multi database in CE")
    database_name = "pastries"
    await adb.cypher_query(f"CREATE DATABASE {database_name} IF NOT EXISTS")
    await adb.close_connection()

    config = get_config()
    # Set database name in url - for url init only
    await adb.set_connection(url=f"{config.database_url}/{database_name}")
    assert await get_current_database_name() == "pastries"

    await adb.close_connection()

    # Set database name in config - for both url and driver init
    config.database_name = database_name

    # url init
    await adb.set_connection(url=config.database_url)
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
    config.database_name = None


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
    # Skip test if Aura credentials are not available (e.g., in external PRs)
    required_env_vars = [
        "AURA_TEST_DB_USER",
        "AURA_TEST_DB_PASSWORD",
        "AURA_TEST_DB_HOSTNAME",
    ]
    missing_vars = [
        var
        for var in required_env_vars
        if var not in os.environ or os.environ[var] == ""
    ]
    if missing_vars:
        pytest.skip(
            f"Skipping Aura test - missing environment variables: {', '.join(missing_vars)}"
        )

    cypher_return = "hello world"
    default_cypher_query = f"RETURN '{cypher_return}'"
    await adb.close_connection()

    await _set_connection(protocol=protocol)
    result, _ = await adb.cypher_query(default_cypher_query)

    assert len(result) > 0
    assert result[0][0] == cypher_return


async def _set_connection(protocol):
    aura_test_db_user = os.environ["AURA_TEST_DB_USER"]
    aura_test_db_password = os.environ["AURA_TEST_DB_PASSWORD"]
    aura_test_db_hostname = os.environ["AURA_TEST_DB_HOSTNAME"]

    database_url = f"{protocol}://{aura_test_db_user}:{aura_test_db_password}@{aura_test_db_hostname}"
    await adb.set_connection(url=database_url)
