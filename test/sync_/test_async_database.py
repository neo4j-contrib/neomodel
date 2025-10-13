# :pylint: disable=protected-access

import asyncio
from test._async_compat import mark_sync_test

import neo4j
import pytest

import neomodel
from neomodel._async_compat.util import Util
from neomodel.sync_.core import Database


def test_neomodel_adb_properties():
    # neomodel.adb is already connected so url, driver, _pid, _database_version and _database_edition are set
    assert neomodel.db._active_transaction is None
    assert neomodel.db._session is None
    assert neomodel.db._database_name is neo4j.DEFAULT_DATABASE
    assert neomodel.db.impersonated_user is None
    assert neomodel.db._parallel_runtime is False


def test_async_database_properties():
    # A fresh instance of AsyncDatabase is not yet connected
    db = Database()
    assert db._active_transaction is None
    assert db.url is None
    assert db.driver is None
    assert db._session is None
    assert db._pid is None
    assert db._database_name is neo4j.DEFAULT_DATABASE
    assert db._database_version is None
    assert db._database_edition is None
    assert db.impersonated_user is None
    assert db._parallel_runtime is False


@mark_sync_test
def test_parallel_transactions():
    if not Util.is_async_code:
        pytest.skip("Async only test")

    transactions = set()
    sessions = set()

    def query(i: int):
        asyncio.sleep(0.05)

        assert neomodel.db._active_transaction is None
        assert neomodel.db._session is None

        with neomodel.db.transaction:
            # ensure transaction and session are unique for async context
            transaction_id = id(neomodel.db._active_transaction)
            assert transaction_id not in transactions
            transactions.add(transaction_id)

            session_id = id(neomodel.db._session)
            assert session_id not in sessions
            sessions.add(session_id)

            result, _ = neomodel.db.cypher_query(
                "CALL apoc.util.sleep($delay_ms) RETURN $task_id as task_id, $delay_ms as slept",
                {"delay_ms": i * 505, "task_id": i},
            )

        return result[0][0], result[0][1], transaction_id, session_id

    results = asyncio.gather(*(query(i) for i in range(1, 5)))
    print("All done:", results)
