import os
from test._async_compat import (
    mark_async_function_auto_fixture,
    mark_sync_session_auto_fixture,
    mark_sync_test,
)
from test.conftest import NEO4J_PASSWORD, NEO4J_URL, NEO4J_USERNAME
from unittest.mock import Mock, patch

import pytest
from neo4j import Driver, GraphDatabase
from neo4j.debug import watch

from neomodel import StringProperty, StructuredNode, db, get_config
from neomodel._async_compat.util import Lock
from neomodel.sync_.connection import ConnectionManager, ensure_connection


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
def test_no_connection_configured_raises():
    # When neither a URL nor a driver is configured, the first query must fail
    # loudly instead of silently connecting with default credentials.
    config = get_config()
    saved_url = config.database_url
    saved_driver = config.driver
    db.close_connection()
    config.database_url = None
    config.driver = None
    try:
        with pytest.raises(ValueError, match="No Neo4j connection has been configured"):
            db.cypher_query("RETURN 1")
    finally:
        config.database_url = saved_url
        config.driver = saved_driver


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
    "url, expected_in_message",
    [
        ("bolt://user:password", "bolt://user:password"),
        ("http://user:password@localhost:7687", "http://user:***@localhost:7687"),
    ],
)
def test_wrong_url_format(url, expected_in_message):
    with pytest.raises(ValueError) as exc_info:
        db.set_connection(url=url)
    message = str(exc_info.value)
    assert "Expecting url format: bolt://user:password@localhost:7687" in message
    assert expected_in_message in message


@mark_sync_test
def test_password_not_leaked_in_wrong_url_error():
    # A malformed but credential-bearing URL must not leak its password into the
    # exception message (which typically ends up in logs / error trackers).
    secret = "sup3rs3cr3t"
    with pytest.raises(ValueError) as exc_info:
        db.set_connection(url=f"http://user:{secret}@localhost:7687")
    assert secret not in str(exc_info.value)


@mark_sync_test
def test_stored_url_has_password_redacted():
    # adb.url is a documented attribute and may be logged/inspected, so the
    # password must not be retained there.
    config = get_config()
    db.set_connection(url=config.database_url)
    assert db.url is not None
    assert NEO4J_PASSWORD not in db.url
    assert ":***@" in db.url
    # The connection must still be usable (retry relies on the private URL).
    assert get_current_database_name() is not None


class _DummyDriver:
    """A stand-in driver so URL parsing can be tested without a live server."""

    def close(self):
        pass


@pytest.fixture
def captured_url_parsing(monkeypatch):
    """Patch driver creation so _parse_driver_from_url can be exercised in
    isolation, capturing the parsed auth and address."""
    from neomodel.sync_ import connection as conn_module

    captured: dict = {}

    def fake_basic_auth(username, password):
        captured["auth"] = (username, password)
        return ("basic_auth", username, password)

    def fake_driver(address, **kwargs):
        captured["address"] = address
        return _DummyDriver()

    monkeypatch.setattr(conn_module, "basic_auth", fake_basic_auth)
    monkeypatch.setattr(conn_module.GraphDatabase, "driver", staticmethod(fake_driver))
    return captured


@mark_sync_test
@pytest.mark.parametrize(
    "url, expected_user, expected_password, expected_address, expected_db",
    [
        # Password containing both "@" and ":" must be parsed verbatim.
        (
            "bolt://user:p@ss:word@localhost:7687/mydb",
            "user",
            "p@ss:word",
            "bolt://localhost:7687",
            "mydb",
        ),
        # Password equal to the username / hostname must not corrupt parsing.
        (
            "bolt://localhost:localhost@localhost:7687",
            "localhost",
            "localhost",
            "bolt://localhost:7687",
            "",
        ),
    ],
)
def test_parse_driver_from_url_handles_tricky_credentials(
    captured_url_parsing,
    url,
    expected_user,
    expected_password,
    expected_address,
    expected_db,
):
    db._parse_driver_from_url(url)
    assert captured_url_parsing["auth"] == (expected_user, expected_password)
    assert captured_url_parsing["address"] == expected_address
    if expected_db:
        assert db._database_name == expected_db
    # The stored public URL must have the password redacted.
    assert ":***@" in db.url


@mark_sync_test
def test_parse_driver_from_url_missing_password_raises():
    # A URL with a username but no password must raise a clear error instead of
    # an opaque unpacking error.
    with pytest.raises(ValueError, match="Expecting url format"):
        db._parse_driver_from_url("bolt://useronly@localhost:7687")


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


# ---------------------------------------------------------------------------
# ensure_connection decorator
# ---------------------------------------------------------------------------


@mark_sync_test
def test_ensure_connection_decorator_no_driver():
    """The decorator lazily connects via the configured URL when no driver is set."""

    class MockDB:
        def __init__(self):
            self.driver = None
            # ensure_connection guards lazy driver creation with this lock.
            self._connection_lock = Lock()

        def set_connection(self, **kwargs):
            pass

        @ensure_connection
        def test_method(self):
            return "success"

    test_db = MockDB()
    with patch.object(
        test_db, "set_connection", new_callable=Mock
    ) as mock_set_connection:
        result = test_db.test_method()
        assert result == "success"
        mock_set_connection.assert_called_once_with(
            url="bolt://neo4j:foobarbaz@localhost:7687"
        )


@mark_sync_test
def test_ensure_connection_decorator_uses_config_driver():
    """When no URL is configured but a driver is, the decorator connects with it."""

    class MockDB:
        def __init__(self):
            self.driver = None
            self._connection_lock = Lock()

        def set_connection(self, **kwargs):
            pass

        @ensure_connection
        def test_method(self):
            return "success"

    config = get_config()
    original_url = config.database_url
    original_driver = config.driver
    sentinel_driver = object()
    try:
        config.database_url = ""
        config.driver = sentinel_driver
        test_db = MockDB()
        with patch.object(
            test_db, "set_connection", new_callable=Mock
        ) as mock_set_connection:
            result = test_db.test_method()
            assert result == "success"
            mock_set_connection.assert_called_once_with(driver=sentinel_driver)
    finally:
        config.database_url = original_url
        config.driver = original_driver


@mark_sync_test
def test_ensure_connection_decorator_with_driver():
    """The decorator is a no-op passthrough when a driver already exists."""

    class MockDB:
        def __init__(self):
            self.driver = "existing_driver"

        @ensure_connection
        def test_method(self):
            return "success"

    test_db = MockDB()
    result = test_db.test_method()
    assert result == "success"


# ---------------------------------------------------------------------------
# Server-version dependent helpers on AsyncConnectionManager
#
# When the server version cannot be determined these must fail with a clear
# RuntimeError rather than returning nonsense. A fresh, unconnected manager
# (with version detection stubbed out) reproduces that state without a server.
# ---------------------------------------------------------------------------


def _manager_without_version():
    manager = ConnectionManager()
    # A truthy driver lets the ensure_connection-decorated helpers run without
    # trying to build a real connection.
    manager.driver = object()
    manager._database_version = None
    manager._database_edition = None
    return manager


@mark_sync_test
def test_get_id_method_raises_without_version():
    manager = _manager_without_version()
    with patch.object(manager, "_update_database_version", new_callable=Mock):
        with pytest.raises(RuntimeError):
            manager.get_id_method()


@mark_sync_test
def test_parse_element_id_none_raises_value_error():
    manager = _manager_without_version()
    with pytest.raises(ValueError, match="Unable to parse element id"):
        manager.parse_element_id(None)


@mark_sync_test
def test_parse_element_id_raises_without_version():
    manager = _manager_without_version()
    with patch.object(manager, "_update_database_version", new_callable=Mock):
        with pytest.raises(RuntimeError):
            manager.parse_element_id("4:abc:0")


@mark_sync_test
def test_version_is_higher_than_raises_without_version():
    manager = _manager_without_version()
    with patch.object(manager, "_update_database_version", new_callable=Mock):
        with pytest.raises(RuntimeError):
            manager.version_is_higher_than("5.0")


@mark_sync_test
def test_edition_is_enterprise_raises_without_version():
    manager = _manager_without_version()
    with patch.object(manager, "_update_database_version", new_callable=Mock):
        with pytest.raises(RuntimeError):
            manager.edition_is_enterprise()
