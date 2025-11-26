import os
from test._async_compat import (
    mark_async_function_auto_fixture,
    mark_sync_session_auto_fixture,
    mark_sync_test,
)
from test.conftest import NEO4J_PASSWORD, NEO4J_URL, NEO4J_USERNAME

import pytest
from neo4j import Driver, GraphDatabase
from neo4j.debug import watch

from neomodel import StringProperty, StructuredNode, db, get_config


@mark_async_function_auto_fixture
def setup_teardown(request):
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
        db.close_connection()
        db.set_connection(url=get_config().database_url)


@mark_sync_session_auto_fixture
def neo4j_logging():
    with watch("neo4j"):
        yield


@mark_sync_test
def get_current_database_name() -> str:
    """
    Fetches the name of the currently active database from the Neo4j database.

    Returns:
    - str: The name of the current database.
    """
    results, meta = db.cypher_query("CALL db.info")
    results_as_dict = [dict(zip(meta, row)) for row in results]

    return results_as_dict[0]["name"]


class Pastry(StructuredNode):
    name = StringProperty(unique_index=True)


@mark_sync_test
def test_set_connection_driver_works():
    # Verify that current connection is up
    assert Pastry(name="Chocolatine").save()
    db.close_connection()

    # Test connection using a driver
    db.set_connection(
        driver=GraphDatabase().driver(NEO4J_URL, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
    )
    assert Pastry(name="Croissant").save()


@mark_sync_test
def test_config_driver_works():
    # Verify that current connection is up
    assert Pastry(name="Chausson aux pommes").save()
    db.close_connection()

    # Test connection using a driver defined in config
    driver: Driver = GraphDatabase().driver(
        NEO4J_URL, auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
    )

    config = get_config()
    config.driver = driver
    assert Pastry(name="Grignette").save()

    # Clear config
    # No need to close connection - pytest teardown will do it
    config.driver = None


@mark_sync_test
def test_connect_to_non_default_database():
    if not db.edition_is_enterprise():
        pytest.skip("Skipping test for community edition - no multi database in CE")
    database_name = "pastries"
    db.cypher_query(f"CREATE DATABASE {database_name} IF NOT EXISTS")
    db.close_connection()

    config = get_config()
    # Set database name in url - for url init only
    db.set_connection(url=f"{config.database_url}/{database_name}")
    assert get_current_database_name() == "pastries"

    db.close_connection()

    # Set database name in config - for both url and driver init
    config.database_name = database_name

    # url init
    db.set_connection(url=config.database_url)
    assert get_current_database_name() == "pastries"

    db.close_connection()

    # driver init
    db.set_connection(
        driver=GraphDatabase().driver(NEO4J_URL, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
    )
    assert get_current_database_name() == "pastries"

    # Clear config
    # No need to close connection - pytest teardown will do it
    config.database_name = None


@mark_sync_test
@pytest.mark.parametrize(
    "url", ["bolt://user:password", "http://user:password@localhost:7687"]
)
def test_wrong_url_format(url):
    with pytest.raises(
        ValueError,
        match=rf"Expecting url format: bolt://user:password@localhost:7687 got {url}",
    ):
        db.set_connection(url=url)


@mark_sync_test
@pytest.mark.parametrize("protocol", ["neo4j+s", "neo4j+ssc", "bolt+s", "bolt+ssc"])
def test_connect_to_aura(protocol):
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
    db.close_connection()

    _set_connection(protocol=protocol)
    result, _ = db.cypher_query(default_cypher_query)

    assert len(result) > 0
    assert result[0][0] == cypher_return


def _set_connection(protocol):
    aura_test_db_user = os.environ["AURA_TEST_DB_USER"]
    aura_test_db_password = os.environ["AURA_TEST_DB_PASSWORD"]
    aura_test_db_hostname = os.environ["AURA_TEST_DB_HOSTNAME"]

    database_url = f"{protocol}://{aura_test_db_user}:{aura_test_db_password}@{aura_test_db_hostname}"
    db.set_connection(url=database_url)
