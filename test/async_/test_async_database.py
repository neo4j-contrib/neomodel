# :pylint: disable=protected-access

import asyncio
from test._async_compat import mark_async_test

import neo4j
import pytest

import neomodel
from neomodel._async_compat.util import AsyncUtil
from neomodel.async_.core import AsyncDatabase


def test_neomodel_adb_properties():
    # neomodel.adb is already connected so url, driver, _pid, _database_version and _database_edition are set
    assert neomodel.adb._active_transaction is None
    assert neomodel.adb._session is None
    assert neomodel.adb._database_name is neo4j.DEFAULT_DATABASE
    assert neomodel.adb.impersonated_user is None
    assert neomodel.adb._parallel_runtime is False


def test_async_database_properties():
    # A fresh instance of AsyncDatabase is not yet connected
    adb = AsyncDatabase()
    assert adb._active_transaction is None
    assert adb.url is None
    assert adb.driver is None
    assert adb._session is None
    assert adb._pid is None
    assert adb._database_name is neo4j.DEFAULT_DATABASE
    assert adb._database_version is None
    assert adb._database_edition is None
    assert adb.impersonated_user is None
    assert adb._parallel_runtime is False


@mark_async_test
async def test_parallel_transactions():
    if not AsyncUtil.is_async_code:
        pytest.skip("Async only test")

    transactions = set()
    sessions = set()

    async def query(i: int):
        await asyncio.sleep(0.05)

        assert neomodel.adb._active_transaction is None
        assert neomodel.adb._session is None

        async with neomodel.adb.transaction:
            # ensure transaction and session are unique for async context
            transaction_id = id(neomodel.adb._active_transaction)
            assert transaction_id not in transactions
            transactions.add(transaction_id)

            session_id = id(neomodel.adb._session)
            assert session_id not in sessions
            sessions.add(session_id)

            result, _ = await neomodel.adb.cypher_query(
                "CALL apoc.util.sleep($delay_ms) RETURN $task_id as task_id, $delay_ms as slept",
                {"delay_ms": i * 505, "task_id": i},
            )

        return result[0][0], result[0][1], transaction_id, session_id

    results = await asyncio.gather(*(query(i) for i in range(1, 5)))
    print("All done:", results)
