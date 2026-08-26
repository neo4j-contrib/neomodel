import asyncio
import contextvars
from test._async_compat import mark_sync_test
from unittest.mock import Mock, patch

import neo4j
import pytest
from neo4j.exceptions import AuthError

from neomodel import (
    IntegerProperty,
    RelationshipTo,
    StringProperty,
    StructuredNode,
    StructuredRel,
    db,
)
from neomodel._async_compat.util import Util
from neomodel.exceptions import FeatureNotSupported
from neomodel.sync_.database import Database


class City(StructuredNode):
    name = StringProperty()


class InCity(StructuredRel):
    creation_year = IntegerProperty(index=True)


class Venue(StructuredNode):
    name = StringProperty(unique_index=True)
    creator = StringProperty(index=True)
    in_city = RelationshipTo(City, relation_type="IN", model=InCity)


@mark_sync_test
def test_clear_database():
    venue = Venue(name="Royal Albert Hall", creator="Queen Victoria").save()
    city = City(name="London").save()
    venue.in_city.connect(city)

    # Clear only the data
    db.clear_neo4j_database()
    database_is_populated, _ = db.cypher_query(
        "MATCH (a) return count(a)>0 as database_is_populated"
    )

    assert database_is_populated[0][0] is False

    db.install_all_labels()
    indexes = db.list_indexes(exclude_token_lookup=True)
    constraints = db.list_constraints()
    assert len(indexes) > 0
    assert len(constraints) > 0

    # Clear constraints and indexes too
    db.clear_neo4j_database(clear_constraints=True, clear_indexes=True)

    indexes = db.list_indexes(exclude_token_lookup=True)
    constraints = db.list_constraints()
    assert len(indexes) == 0
    assert len(constraints) == 0


@mark_sync_test
def test_change_password():
    prev_password = "foobarbaz"
    new_password = "newpassword"
    prev_url = f"bolt://neo4j:{prev_password}@localhost:7687"
    new_url = f"bolt://neo4j:{new_password}@localhost:7687"

    db.change_neo4j_password("neo4j", new_password)
    db.close_connection()

    db.set_connection(url=new_url)
    db.close_connection()

    with pytest.raises(AuthError):
        db.set_connection(url=prev_url)

    db.close_connection()

    db.set_connection(url=new_url)
    db.change_neo4j_password("neo4j", prev_password)
    db.close_connection()

    db.set_connection(url=prev_url)


@mark_sync_test
def test_change_password_is_not_injectable():
    """change_neo4j_password must parameterize the password and escape the
    username so neither can break out of the Cypher statement."""
    test_db = Database()

    # Both values contain characters that would break a naive f-string and
    # let an attacker execute arbitrary admin Cypher.
    malicious_user = "admin` SET PASSWORD 'pwned"
    malicious_password = "secret' SET ROLE admin //"

    with patch.object(test_db._query, "cypher_query", new_callable=Mock) as mock_cypher:
        test_db.change_neo4j_password(malicious_user, malicious_password)

    query, params = mock_cypher.call_args.args[:2]

    # The password is bound as a parameter, never interpolated into the query.
    assert params == {"password": malicious_password}
    assert "$password" in query
    assert malicious_password not in query

    # The username is escaped as a single backtick-quoted identifier: any
    # backtick it contains is doubled, so it cannot terminate the identifier.
    assert query == "ALTER USER `admin`` SET PASSWORD 'pwned` SET PASSWORD $password"


@mark_sync_test
def test_adb_singleton_behavior():
    """Test that Database enforces singleton behavior."""

    # Get the module-level instance
    adb1 = Database.get_instance()

    # Try to create another instance directly
    adb2 = Database()

    # Try to create another instance via get_instance
    adb3 = Database.get_instance()

    # All instances should be the same object
    assert adb1 is adb2, "Direct instantiation should return the same instance"
    assert adb1 is adb3, "get_instance should return the same instance"
    assert adb2 is adb3, "All instances should be the same object"

    # Test that the module-level 'adb' is also the same instance
    assert db is adb1, "Module-level 'db' should be the same instance"


@mark_sync_test
def test_async_database_properties():
    # A fresh instance of AsyncDatabase is not yet connected
    Database.reset_instance()
    reset_singleton = Database.get_instance()
    assert reset_singleton._active_transaction is None
    assert reset_singleton.url is None
    assert reset_singleton.driver is None
    assert reset_singleton._session is None
    assert reset_singleton._database_name is neo4j.DEFAULT_DATABASE
    assert reset_singleton._database_version is None
    assert reset_singleton._database_edition is None
    assert reset_singleton.impersonated_user is None
    assert reset_singleton._parallel_runtime is False


@mark_sync_test
def test_parallel_transactions():
    if not Util.is_async_code:
        pytest.skip("Async only test")

    transactions = set()
    sessions = set()

    def query(i: int):
        asyncio.sleep(0.05)

        assert db._active_transaction is None
        assert db._session is None

        with db.transaction:
            # ensure transaction and session are unique for async context
            transaction_id = id(db._active_transaction)
            assert transaction_id not in transactions
            transactions.add(transaction_id)

            session_id = id(db._session)
            assert session_id not in sessions
            sessions.add(session_id)

            result, _ = db.cypher_query(
                "CALL apoc.util.sleep($delay_ms) RETURN $task_id as task_id, $delay_ms as slept",
                {"delay_ms": i * 505, "task_id": i},
            )

        return result[0][0], result[0][1], transaction_id, session_id

    _ = asyncio.gather(*(query(i) for i in range(1, 5)))


@mark_sync_test
def test_driver_state_is_process_global():
    # Ensure the singleton is connected.
    db.cypher_query("RETURN 1")

    driver = db.driver
    version = db._database_version
    edition = db._database_edition
    assert driver is not None

    # A brand-new context - as seen by a fresh OS thread, or a task that did not
    # inherit this context - must observe the SAME process-wide driver and
    # server facts, rather than finding them unset and rebuilding a separate
    # driver/connection pool.
    fresh_context = contextvars.Context()
    assert fresh_context.run(lambda: db.driver) is driver
    assert fresh_context.run(lambda: db._database_version) == version
    assert fresh_context.run(lambda: db._database_edition) == edition

    # Per-context state, by contrast, stays isolated: a fresh context sees the
    # defaults, not whatever the current context happens to hold.
    assert fresh_context.run(lambda: db._session) is None
    assert fresh_context.run(lambda: db._active_transaction) is None


# ---------------------------------------------------------------------------
# Schema management delegated through the facade
#
# These exercise the AsyncDatabase facade -> AsyncSchemaManager wiring against
# mocks so they do not depend on what is actually installed in the database.
# ---------------------------------------------------------------------------


@mark_sync_test
def test_clear_neo4j_database():
    """clear_neo4j_database clears data and optionally constraints/indexes."""
    test_db = Database()

    with patch.object(test_db._query, "cypher_query", new_callable=Mock) as mock_cypher:
        with patch.object(
            test_db._schema, "drop_constraints", new_callable=Mock
        ) as mock_drop_constraints:
            with patch.object(
                test_db._schema, "drop_indexes", new_callable=Mock
            ) as mock_drop_indexes:
                test_db.clear_neo4j_database(clear_constraints=True, clear_indexes=True)

                mock_cypher.assert_called_once()
                mock_drop_constraints.assert_called_once()
                mock_drop_indexes.assert_called_once()


@mark_sync_test
def test_drop_constraints():
    """drop_constraints lists then drops each constraint."""
    test_db = Database()

    mock_results = [
        {"name": "constraint1", "labelsOrTypes": ["Label1"], "properties": ["prop1"]},
        {"name": "constraint2", "labelsOrTypes": ["Label2"], "properties": ["prop2"]},
    ]

    with patch.object(test_db._query, "cypher_query", new_callable=Mock) as mock_cypher:
        mock_cypher.return_value = (
            mock_results,
            ["name", "labelsOrTypes", "properties"],
        )

        test_db.drop_constraints(quiet=False)

        # 1 call to list constraints + 1 drop per constraint.
        assert mock_cypher.call_count == 3


@mark_sync_test
def test_drop_indexes():
    """drop_indexes drops each listed index."""
    test_db = Database()

    mock_indexes = [
        {"name": "index1", "labelsOrTypes": ["Label1"], "properties": ["prop1"]},
        {"name": "index2", "labelsOrTypes": ["Label2"], "properties": ["prop2"]},
    ]

    with patch.object(
        test_db._schema, "list_indexes", new_callable=Mock
    ) as mock_list_indexes:
        mock_list_indexes.return_value = mock_indexes

        with patch.object(
            test_db._query, "cypher_query", new_callable=Mock
        ) as mock_cypher:
            test_db.drop_indexes(quiet=False)

            assert mock_cypher.call_count == 2


@mark_sync_test
def test_remove_all_labels():
    """remove_all_labels drops both constraints and indexes."""
    test_db = Database()

    with patch.object(
        test_db._schema, "drop_constraints", new_callable=Mock
    ) as mock_drop_constraints:
        with patch.object(
            test_db._schema, "drop_indexes", new_callable=Mock
        ) as mock_drop_indexes:
            with patch("sys.stdout") as mock_stdout:
                test_db.remove_all_labels()

                mock_drop_constraints.assert_called_once_with(
                    quiet=False, stdout=mock_stdout
                )
                mock_drop_indexes.assert_called_once_with(
                    quiet=False, stdout=mock_stdout
                )


@mark_sync_test
def test_install_all_labels():
    """install_all_labels installs labels for each registered node class."""
    test_db = Database()

    class MockNode:
        def __init__(self, name):
            self.__name__ = name

        @classmethod
        def install_labels(cls, quiet=True, stdout=None):
            pass

    with patch("neomodel.sync_.node.StructuredNode", MockNode):
        with patch("sys.stdout"):
            test_db.install_all_labels()


# ---------------------------------------------------------------------------
# Facade behaviour
# ---------------------------------------------------------------------------


@mark_sync_test
def test_impersonate_requires_enterprise_edition():
    """Impersonation is an enterprise-only feature: on a non-enterprise edition
    it must raise FeatureNotSupported rather than silently issuing impersonated
    queries. The edition is stubbed so the check is deterministic regardless of
    the server the tests run against."""
    db = Database()
    original_edition = db._database_edition
    try:
        # A non-None edition short-circuits the lazy server lookup.
        db._database_edition = "community"
        with pytest.raises(FeatureNotSupported):
            db.impersonate("somebody")
    finally:
        db._database_edition = original_edition


@mark_sync_test
def test_facade_delegates_state_to_connection_manager():
    """The Database facade reads and writes shared connection state through
    its ConnectionManager rather than holding any of its own."""
    db = Database()
    connection = db._connection

    # Getters read straight from the connection manager.
    assert db.driver is connection.driver
    assert db._owns_driver is connection._owns_driver
    assert db._connection_lock is connection._connection_lock
    assert db._connection_url == connection._connection_url

    # Setters write through to the connection manager. Capture and restore the
    # originals so the shared singleton is left untouched for other tests.
    originals = {
        name: getattr(connection, name)
        for name in (
            "url",
            "_connection_url",
            "_database_version",
            "_database_edition",
            "_database_name",
            "_active_transaction",
            "_session",
            "_owns_driver",
        )
    }
    try:
        # Round-trip the driver through the setter without changing it.
        db.driver = connection.driver
        assert db.driver is connection.driver

        db.url = "redacted://url"
        db._connection_url = "bolt://user:pass@localhost:7687"
        db._database_version = "5.99.0"
        db._database_edition = "enterprise"
        db._database_name = "facade-test-db"
        db._active_transaction = "tx-sentinel"
        db._session = "session-sentinel"
        db._owns_driver = not originals["_owns_driver"]

        assert connection.url == "redacted://url"
        assert connection._connection_url == "bolt://user:pass@localhost:7687"
        assert connection._database_version == "5.99.0"
        assert connection._database_edition == "enterprise"
        assert connection._database_name == "facade-test-db"
        assert connection._active_transaction == "tx-sentinel"
        assert connection._session == "session-sentinel"
        assert connection._owns_driver == (not originals["_owns_driver"])
    finally:
        for name, value in originals.items():
            setattr(connection, name, value)
