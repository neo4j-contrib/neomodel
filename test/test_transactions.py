import pytest
from neo4j.api import Bookmarks
from neo4j.exceptions import ClientError, TransactionError
from pytest import raises

from neomodel import StringProperty, StructuredNodeAsync, UniqueProperty
from neomodel._async.core import adb


class APerson(StructuredNodeAsync):
    name = StringProperty(unique_index=True)


def test_rollback_and_commit_transaction():
    for p in APerson.nodes:
        p.delete()

    APerson(name="Roger").save_async()

    adb.begin()
    APerson(name="Terry S").save_async()
    adb.rollback()

    assert len(APerson.nodes) == 1

    adb.begin()
    APerson(name="Terry S").save_async()
    adb.commit()

    assert len(APerson.nodes) == 2


@adb.transaction
def in_a_tx(*names):
    for n in names:
        APerson(name=n).save_async()


def test_transaction_decorator():
    adb.install_labels_async(APerson)
    for p in APerson.nodes:
        p.delete()

    # should work
    in_a_tx("Roger")
    assert True

    # should bail but raise correct error
    with raises(UniqueProperty):
        in_a_tx("Jim", "Roger")

    assert "Jim" not in [p.name for p in APerson.nodes]


def test_transaction_as_a_context():
    with adb.transaction:
        APerson(name="Tim").save_async()

    assert APerson.nodes.filter(name="Tim")

    with raises(UniqueProperty):
        with adb.transaction:
            APerson(name="Tim").save_async()


def test_query_inside_transaction():
    for p in APerson.nodes:
        p.delete()

    with adb.transaction:
        APerson(name="Alice").save_async()
        APerson(name="Bob").save_async()

        assert len([p.name for p in APerson.nodes]) == 2


def test_read_transaction():
    APerson(name="Johnny").save_async()

    with adb.read_transaction:
        people = APerson.nodes.all()
        assert people

    with raises(TransactionError):
        with adb.read_transaction:
            with raises(ClientError) as e:
                APerson(name="Gina").save_async()
            assert e.value.code == "Neo.ClientError.Statement.AccessMode"


def test_write_transaction():
    with adb.write_transaction:
        APerson(name="Amelia").save_async()

    amelia = APerson.nodes.get(name="Amelia")
    assert amelia


def double_transaction():
    adb.begin()
    with raises(SystemError, match=r"Transaction in progress"):
        adb.begin()

    adb.rollback()


@adb.transaction.with_bookmark
def in_a_tx(*names):
    for n in names:
        APerson(name=n).save_async()


def test_bookmark_transaction_decorator():
    for p in APerson.nodes:
        p.delete()

    # should work
    result, bookmarks = in_a_tx("Ruth", bookmarks=None)
    assert result is None
    assert isinstance(bookmarks, Bookmarks)

    # should bail but raise correct error
    with raises(UniqueProperty):
        in_a_tx("Jane", "Ruth")

    assert "Jane" not in [p.name for p in APerson.nodes]


def test_bookmark_transaction_as_a_context():
    with adb.transaction as transaction:
        APerson(name="Tanya").save_async()
    assert isinstance(transaction.last_bookmark, Bookmarks)

    assert APerson.nodes.filter(name="Tanya")

    with raises(UniqueProperty):
        with adb.transaction as transaction:
            APerson(name="Tanya").save_async()
    assert not hasattr(transaction, "last_bookmark")


@pytest.fixture
def spy_on_db_begin(monkeypatch):
    spy_calls = []
    original_begin = adb.begin

    def begin_spy(*args, **kwargs):
        spy_calls.append((args, kwargs))
        return original_begin(*args, **kwargs)

    monkeypatch.setattr(adb, "begin", begin_spy)
    return spy_calls


def test_bookmark_passed_in_to_context(spy_on_db_begin):
    transaction = adb.transaction
    with transaction:
        pass

    assert spy_on_db_begin[-1] == ((), {"access_mode": None, "bookmarks": None})
    last_bookmark = transaction.last_bookmark

    transaction.bookmarks = last_bookmark
    with transaction:
        pass
    assert spy_on_db_begin[-1] == (
        (),
        {"access_mode": None, "bookmarks": last_bookmark},
    )


def test_query_inside_bookmark_transaction():
    for p in APerson.nodes:
        p.delete()

    with adb.transaction as transaction:
        APerson(name="Alice").save_async()
        APerson(name="Bob").save_async()

        assert len([p.name for p in APerson.nodes]) == 2

    assert isinstance(transaction.last_bookmark, Bookmarks)
