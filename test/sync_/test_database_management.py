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
from neomodel.sync_.database import Database, _redact_params


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

    with patch.object(test_db, "cypher_query", new_callable=Mock) as mock_cypher:
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
def test_redact_params_masks_password():
    """Sensitive parameter values must be masked before being logged."""
    assert _redact_params({"password": "supersecret", "user": "neo4j"}) == {
        "password": "******",
        "user": "neo4j",
    }
    # The real secret never appears in the redacted output.
    assert "supersecret" not in repr(_redact_params({"password": "supersecret"}))
    # Empty / missing params are passed through untouched.
    assert _redact_params(None) is None
    assert _redact_params({}) == {}


@mark_sync_test
def test_redact_params_matches_sensitive_key_variants():
    """A range of secret-bearing key names should be masked, including
    compound and differently-cased variants."""
    # Use distinctive values that cannot appear as substrings of the (unredacted)
    # keys, so the leak check below is meaningful.
    sensitive = {
        "pwd": "secret-value-pwd",
        "Password": "secret-value-password",
        "user_password": "secret-value-user-password",
        "API_KEY": "secret-value-api-key",
        "stripe_api_key": "secret-value-stripe-api-key",
        "refresh_token": "secret-value-refresh-token",
        "client_secret": "secret-value-client-secret",
        "authorization": "secret-value-authorization",
        "otp": "secret-value-otp",
        "ssn": "secret-value-ssn",
    }
    redacted = _redact_params(sensitive)
    assert all(value == "******" for value in redacted.values()), redacted
    for original_value in sensitive.values():
        assert original_value not in repr(redacted)


@mark_sync_test
def test_redact_params_does_not_over_redact():
    """Substring matching must not flag innocuous keys that merely contain a
    sensitive token as a fragment (e.g. 'author' contains 'auth')."""
    benign = {
        "author": "alice",
        "passenger": "bob",
        "monkey": "george",
        "user": "neo4j",
        "name": "thing",
    }
    assert _redact_params(benign) == benign


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
