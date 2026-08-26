from test._async_compat import mark_async_test
from unittest.mock import AsyncMock, patch

import pytest
from neo4j.api import Bookmarks
from neo4j.exceptions import ClientError, TransactionError
from pytest import raises

from neomodel import AsyncStructuredNode, StringProperty, UniqueProperty, adb
from neomodel.async_.database import AsyncDatabase
from neomodel.async_.transaction import AsyncTransactionProxy
from neomodel.config import get_config


class APerson(AsyncStructuredNode):
    name = StringProperty(unique_index=True)


@mark_async_test
async def test_rollback_and_commit_transaction():
    await APerson(name="Roger").save()

    await adb.begin()
    await APerson(name="Terry S").save()
    await adb.rollback()

    assert len(await APerson.nodes) == 1

    await adb.begin()
    await APerson(name="Terry S").save()
    await adb.commit()

    assert len(await APerson.nodes) == 2


@adb.transaction
async def in_a_tx(*names):
    for n in names:
        await APerson(name=n).save()


@mark_async_test
async def test_transaction_decorator():
    await adb.install_labels(APerson)

    # should work
    await in_a_tx("Roger")

    # should bail but raise correct error
    with raises(UniqueProperty):
        await in_a_tx("Jim", "Roger")

    assert "Jim" not in [p.name for p in await APerson.nodes]


@mark_async_test
async def test_transaction_as_a_context():
    async with adb.transaction:
        await APerson(name="Tim").save()

    assert await APerson.nodes.filter(name="Tim")

    with raises(UniqueProperty):
        async with adb.transaction:
            await APerson(name="Tim").save()


@mark_async_test
async def test_query_inside_transaction():
    async with adb.transaction:
        await APerson(name="Alice").save()
        await APerson(name="Bob").save()

        assert len([p.name for p in await APerson.nodes]) == 2


@mark_async_test
async def test_read_transaction():
    await APerson(name="Johnny").save()

    async with adb.read_transaction:
        people = await APerson.nodes
        assert people

    with raises(TransactionError):
        async with adb.read_transaction:
            with raises(ClientError) as e:
                await APerson(name="Gina").save()
            assert e.value.code == "Neo.ClientError.Statement.AccessMode"


@mark_async_test
async def test_write_transaction():
    async with adb.write_transaction:
        await APerson(name="Amelia").save()

    amelia = await APerson.nodes.get(name="Amelia")
    assert amelia


@mark_async_test
async def test_double_transaction():
    await adb.begin()
    with raises(SystemError, match=r"Transaction in progress"):
        await adb.begin()

    await adb.rollback()


@adb.transaction.with_bookmark
async def in_a_tx_with_bookmark(*names):
    for n in names:
        await APerson(name=n).save()


@mark_async_test
async def test_bookmark_transaction_decorator():
    # should work
    result, bookmarks = await in_a_tx_with_bookmark("Ruth", bookmarks=None)
    assert result is None
    assert isinstance(bookmarks, Bookmarks)

    # should bail but raise correct error
    with raises(UniqueProperty):
        await in_a_tx_with_bookmark("Jane", "Ruth")

    assert "Jane" not in [p.name for p in await APerson.nodes]


@mark_async_test
async def test_bookmark_transaction_as_a_context():
    async with adb.transaction as transaction:
        await APerson(name="Tanya").save()
    assert isinstance(transaction.last_bookmarks, Bookmarks)

    assert await APerson.nodes.filter(name="Tanya")

    with raises(UniqueProperty):
        async with adb.transaction as transaction:
            await APerson(name="Tanya").save()
    assert transaction.last_bookmarks is None


@pytest.fixture
def spy_on_db_begin(monkeypatch):
    spy_calls = []
    original_begin = adb.begin

    def begin_spy(*args, **kwargs):
        spy_calls.append((args, kwargs))
        return original_begin(*args, **kwargs)

    monkeypatch.setattr(adb, "begin", begin_spy)
    return spy_calls


@mark_async_test
async def test_bookmark_passed_in_to_context(spy_on_db_begin):
    transaction = adb.transaction
    async with transaction:
        pass

    assert (spy_on_db_begin)[-1] == (
        (),
        {"access_mode": None, "bookmarks": None, "timeout": None},
    )
    last_bookmarks = transaction.last_bookmarks

    transaction.bookmarks = last_bookmarks
    async with transaction:
        pass
    assert spy_on_db_begin[-1] == (
        (),
        {"access_mode": None, "bookmarks": last_bookmarks, "timeout": None},
    )


@mark_async_test
async def test_query_inside_bookmark_transaction():
    async with adb.transaction as transaction:
        await APerson(name="Alice").save()
        await APerson(name="Bob").save()

        assert len([p.name for p in await APerson.nodes]) == 2

    assert isinstance(transaction.last_bookmarks, Bookmarks)


@mark_async_test
async def test_transaction_timeout_default(spy_on_db_begin):
    async with adb.transaction:
        pass

    assert spy_on_db_begin[-1] == (
        (),
        {"access_mode": None, "bookmarks": None, "timeout": None},
    )


@mark_async_test
async def test_transaction_timeout_explicit(spy_on_db_begin):
    await adb.begin(timeout=7.5)
    await adb.rollback()

    assert spy_on_db_begin[-1] == ((), {"timeout": 7.5})


@mark_async_test
async def test_transaction_timeout_fires():
    with raises(ClientError, match="TransactionTimedOut"):
        async with adb.transaction(timeout=1):
            await adb.cypher_query("CALL apoc.util.sleep(3000)")


@mark_async_test
async def test_transaction_timeout_via_config_fires(spy_on_db_begin):
    config = get_config()
    original = config.transaction_timeout
    try:
        config.transaction_timeout = 1.42
        with raises(ClientError, match="TransactionTimedOut"):
            async with adb.transaction:
                await adb.cypher_query("CALL apoc.util.sleep(3000)")
    finally:
        config.transaction_timeout = original


@mark_async_test
async def test_transaction_timeout_succeeds():
    async with adb.transaction(timeout=2):
        await adb.cypher_query("CALL apoc.util.sleep(500)")


@mark_async_test
async def test_transaction_timeout_as_decorator(spy_on_db_begin):
    @adb.transaction(timeout=4.2)
    async def run_in_transaction():
        await adb.cypher_query("RETURN 1")

    await run_in_transaction()

    assert spy_on_db_begin[-1] == (
        (),
        {"access_mode": None, "bookmarks": None, "timeout": 4.2},
    )


# ---------------------------------------------------------------------------
# AsyncTransactionProxy unit tests
# ---------------------------------------------------------------------------


@mark_async_test
async def test_proxy_aenter_parallel_runtime_warning():
    """Entering a parallel-runtime proxy on a server that does not support it
    warns and still begins the transaction."""
    test_db = AsyncDatabase()
    proxy = AsyncTransactionProxy(test_db, parallel_runtime=True)

    with patch.object(
        test_db, "parallel_runtime_available", new_callable=AsyncMock
    ) as mock_available:
        mock_available.return_value = False

        with patch("warnings.warn") as mock_warn:
            with patch.object(test_db, "begin", new_callable=AsyncMock) as mock_begin:
                await proxy.__aenter__()

                parallel_runtime_calls = [
                    call
                    for call in mock_warn.call_args_list
                    if "Parallel runtime is only available" in str(call[0][0])
                ]
                assert len(parallel_runtime_calls) == 1
                mock_begin.assert_called_once()


@mark_async_test
async def test_proxy_aexit_with_exception():
    """An exception inside the context rolls back instead of committing."""
    test_db = AsyncDatabase()
    proxy = AsyncTransactionProxy(test_db)

    with patch.object(test_db, "rollback", new_callable=AsyncMock) as mock_rollback:
        with patch.object(test_db, "commit", new_callable=AsyncMock) as mock_commit:
            await proxy.__aexit__(ValueError, ValueError("test"), None)
            mock_rollback.assert_called_once()
            mock_commit.assert_not_called()


@mark_async_test
async def test_proxy_aexit_success():
    """A clean exit commits and records the returned bookmarks."""
    test_db = AsyncDatabase()
    proxy = AsyncTransactionProxy(test_db)

    with patch.object(test_db, "rollback", new_callable=AsyncMock) as mock_rollback:
        with patch.object(test_db, "commit", new_callable=AsyncMock) as mock_commit:
            mock_commit.return_value = "bookmarks"

            await proxy.__aexit__(None, None, None)
            mock_rollback.assert_not_called()
            mock_commit.assert_called_once()
            assert proxy.last_bookmarks == "bookmarks"


@mark_async_test
async def test_proxy_call_decorator():
    """Using the proxy as a decorator wraps the call in the transaction."""
    test_db = AsyncDatabase()
    proxy = AsyncTransactionProxy(test_db)

    async def test_func():
        return "success"

    decorated = proxy(test_func)
    assert callable(decorated)

    with patch.object(proxy, "__aenter__", new_callable=AsyncMock) as mock_enter:
        with patch.object(proxy, "__aexit__", new_callable=AsyncMock):
            mock_enter.return_value = proxy
            result = await decorated()
            assert result == "success"


@mark_async_test
async def test_commit_without_transaction_raises():
    # Calling commit with no active transaction must raise a clear error rather
    # than an AttributeError on None (and must not vanish under python -O - see
    # test_optimized_mode_checks.py).
    assert adb._active_transaction is None
    with raises(RuntimeError, match="No transaction in progress"):
        await adb.commit()


@mark_async_test
async def test_rollback_without_transaction_raises():
    assert adb._active_transaction is None
    with raises(RuntimeError, match="No transaction in progress"):
        await adb.rollback()
