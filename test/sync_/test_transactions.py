from test._async_compat import mark_sync_test
from unittest.mock import Mock, patch

import pytest
from neo4j.api import Bookmarks
from neo4j.exceptions import ClientError, TransactionError
from pytest import raises

from neomodel import StringProperty, StructuredNode, UniqueProperty, db
from neomodel.config import get_config
from neomodel.sync_.database import Database
from neomodel.sync_.transaction import TransactionProxy


class APerson(StructuredNode):
    name = StringProperty(unique_index=True)


@mark_sync_test
def test_rollback_and_commit_transaction():
    APerson(name="Roger").save()

    db.begin()
    APerson(name="Terry S").save()
    db.rollback()

    assert len(APerson.nodes) == 1

    db.begin()
    APerson(name="Terry S").save()
    db.commit()

    assert len(APerson.nodes) == 2


@db.transaction
def in_a_tx(*names):
    for n in names:
        APerson(name=n).save()


@mark_sync_test
def test_transaction_decorator():
    db.install_labels(APerson)

    # should work
    in_a_tx("Roger")

    # should bail but raise correct error
    with raises(UniqueProperty):
        in_a_tx("Jim", "Roger")

    assert "Jim" not in [p.name for p in APerson.nodes]


@mark_sync_test
def test_transaction_as_a_context():
    with db.transaction:
        APerson(name="Tim").save()

    assert APerson.nodes.filter(name="Tim")

    with raises(UniqueProperty):
        with db.transaction:
            APerson(name="Tim").save()


@mark_sync_test
def test_query_inside_transaction():
    with db.transaction:
        APerson(name="Alice").save()
        APerson(name="Bob").save()

        assert len([p.name for p in APerson.nodes]) == 2


@mark_sync_test
def test_read_transaction():
    APerson(name="Johnny").save()

    with db.read_transaction:
        people = APerson.nodes
        assert people

    with raises(TransactionError):
        with db.read_transaction:
            with raises(ClientError) as e:
                APerson(name="Gina").save()
            assert e.value.code == "Neo.ClientError.Statement.AccessMode"


@mark_sync_test
def test_write_transaction():
    with db.write_transaction:
        APerson(name="Amelia").save()

    amelia = APerson.nodes.get(name="Amelia")
    assert amelia


@mark_sync_test
def test_double_transaction():
    db.begin()
    with raises(SystemError, match=r"Transaction in progress"):
        db.begin()

    db.rollback()


@db.transaction.with_bookmark
def in_a_tx_with_bookmark(*names):
    for n in names:
        APerson(name=n).save()


@mark_sync_test
def test_bookmark_transaction_decorator():
    # should work
    result, bookmarks = in_a_tx_with_bookmark("Ruth", bookmarks=None)
    assert result is None
    assert isinstance(bookmarks, Bookmarks)

    # should bail but raise correct error
    with raises(UniqueProperty):
        in_a_tx_with_bookmark("Jane", "Ruth")

    assert "Jane" not in [p.name for p in APerson.nodes]


@mark_sync_test
def test_bookmark_transaction_as_a_context():
    with db.transaction as transaction:
        APerson(name="Tanya").save()
    assert isinstance(transaction.last_bookmarks, Bookmarks)

    assert APerson.nodes.filter(name="Tanya")

    with raises(UniqueProperty):
        with db.transaction as transaction:
            APerson(name="Tanya").save()
    assert transaction.last_bookmarks is None


@pytest.fixture
def spy_on_db_begin(monkeypatch):
    spy_calls = []
    original_begin = db.begin

    def begin_spy(*args, **kwargs):
        spy_calls.append((args, kwargs))
        return original_begin(*args, **kwargs)

    monkeypatch.setattr(db, "begin", begin_spy)
    return spy_calls


@mark_sync_test
def test_bookmark_passed_in_to_context(spy_on_db_begin):
    transaction = db.transaction
    with transaction:
        pass

    assert (spy_on_db_begin)[-1] == (
        (),
        {"access_mode": None, "bookmarks": None, "timeout": None},
    )
    last_bookmarks = transaction.last_bookmarks

    transaction.bookmarks = last_bookmarks
    with transaction:
        pass
    assert spy_on_db_begin[-1] == (
        (),
        {"access_mode": None, "bookmarks": last_bookmarks, "timeout": None},
    )


@mark_sync_test
def test_query_inside_bookmark_transaction():
    with db.transaction as transaction:
        APerson(name="Alice").save()
        APerson(name="Bob").save()

        assert len([p.name for p in APerson.nodes]) == 2

    assert isinstance(transaction.last_bookmarks, Bookmarks)


@mark_sync_test
def test_transaction_timeout_default(spy_on_db_begin):
    with db.transaction:
        pass

    assert spy_on_db_begin[-1] == (
        (),
        {"access_mode": None, "bookmarks": None, "timeout": None},
    )


@mark_sync_test
def test_transaction_timeout_explicit(spy_on_db_begin):
    db.begin(timeout=7.5)
    db.rollback()

    assert spy_on_db_begin[-1] == ((), {"timeout": 7.5})


@mark_sync_test
def test_transaction_timeout_fires():
    with raises(ClientError, match="TransactionTimedOut"):
        with db.transaction(timeout=1):
            db.cypher_query("CALL apoc.util.sleep(3000)")


@mark_sync_test
def test_transaction_timeout_via_config_fires(spy_on_db_begin):
    config = get_config()
    original = config.transaction_timeout
    try:
        config.transaction_timeout = 1.42
        with raises(ClientError, match="TransactionTimedOut"):
            with db.transaction:
                db.cypher_query("CALL apoc.util.sleep(3000)")
    finally:
        config.transaction_timeout = original


@mark_sync_test
def test_transaction_timeout_succeeds():
    with db.transaction(timeout=2):
        db.cypher_query("CALL apoc.util.sleep(500)")


@mark_sync_test
def test_transaction_timeout_as_decorator(spy_on_db_begin):
    @db.transaction(timeout=4.2)
    def run_in_transaction():
        db.cypher_query("RETURN 1")

    run_in_transaction()

    assert spy_on_db_begin[-1] == (
        (),
        {"access_mode": None, "bookmarks": None, "timeout": 4.2},
    )


# ---------------------------------------------------------------------------
# AsyncTransactionProxy unit tests
# ---------------------------------------------------------------------------


@mark_sync_test
def test_proxy_aenter_parallel_runtime_warning():
    """Entering a parallel-runtime proxy on a server that does not support it
    warns and still begins the transaction."""
    test_db = Database()
    proxy = TransactionProxy(test_db, parallel_runtime=True)

    with patch.object(
        test_db, "parallel_runtime_available", new_callable=Mock
    ) as mock_available:
        mock_available.return_value = False

        with patch("warnings.warn") as mock_warn:
            with patch.object(test_db, "begin", new_callable=Mock) as mock_begin:
                proxy.__enter__()

                parallel_runtime_calls = [
                    call
                    for call in mock_warn.call_args_list
                    if "Parallel runtime is only available" in str(call[0][0])
                ]
                assert len(parallel_runtime_calls) == 1
                mock_begin.assert_called_once()


@mark_sync_test
def test_proxy_aexit_with_exception():
    """An exception inside the context rolls back instead of committing."""
    test_db = Database()
    proxy = TransactionProxy(test_db)

    with patch.object(test_db, "rollback", new_callable=Mock) as mock_rollback:
        with patch.object(test_db, "commit", new_callable=Mock) as mock_commit:
            proxy.__exit__(ValueError, ValueError("test"), None)
            mock_rollback.assert_called_once()
            mock_commit.assert_not_called()


@mark_sync_test
def test_proxy_aexit_success():
    """A clean exit commits and records the returned bookmarks."""
    test_db = Database()
    proxy = TransactionProxy(test_db)

    with patch.object(test_db, "rollback", new_callable=Mock) as mock_rollback:
        with patch.object(test_db, "commit", new_callable=Mock) as mock_commit:
            mock_commit.return_value = "bookmarks"

            proxy.__exit__(None, None, None)
            mock_rollback.assert_not_called()
            mock_commit.assert_called_once()
            assert proxy.last_bookmarks == "bookmarks"


@mark_sync_test
def test_proxy_call_decorator():
    """Using the proxy as a decorator wraps the call in the transaction."""
    test_db = Database()
    proxy = TransactionProxy(test_db)

    def test_func():
        return "success"

    decorated = proxy(test_func)
    assert callable(decorated)

    with patch.object(proxy, "__enter__", new_callable=Mock) as mock_enter:
        with patch.object(proxy, "__exit__", new_callable=Mock):
            mock_enter.return_value = proxy
            result = decorated()
            assert result == "success"


@mark_sync_test
def test_commit_without_transaction_raises():
    # Calling commit with no active transaction must raise a clear error rather
    # than an AttributeError on None (and must not vanish under python -O - see
    # test_optimized_mode_checks.py).
    assert db._active_transaction is None
    with raises(RuntimeError, match="No transaction in progress"):
        db.commit()


@mark_sync_test
def test_rollback_without_transaction_raises():
    assert db._active_transaction is None
    with raises(RuntimeError, match="No transaction in progress"):
        db.rollback()
