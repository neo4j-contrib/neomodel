from test._async_compat import mark_sync_test

import pytest
from neo4j.api import Bookmarks
from neo4j.exceptions import ClientError, TransactionError
from pytest import raises

from neomodel import StringProperty, StructuredNode, UniqueProperty, db


class APerson(StructuredNode):
    name = StringProperty(unique_index=True)


@mark_sync_test
def test_rollback_and_commit_transaction():
    for p in APerson.nodes:
        p.delete()

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
    for p in APerson.nodes:
        p.delete()

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
    for p in APerson.nodes:
        p.delete()

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
def double_transaction():
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
    for p in APerson.nodes:
        p.delete()

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
    assert isinstance(transaction.last_bookmark, Bookmarks)

    assert APerson.nodes.filter(name="Tanya")

    with raises(UniqueProperty):
        with db.transaction as transaction:
            APerson(name="Tanya").save()
    assert not hasattr(transaction, "last_bookmark")


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

    assert (spy_on_db_begin)[-1] == ((), {"access_mode": None, "bookmarks": None})
    last_bookmark = transaction.last_bookmark

    transaction.bookmarks = last_bookmark
    with transaction:
        pass
    assert spy_on_db_begin[-1] == (
        (),
        {"access_mode": None, "bookmarks": last_bookmark},
    )


@mark_sync_test
def test_query_inside_bookmark_transaction():
    for p in APerson.nodes:
        p.delete()

    with db.transaction as transaction:
        APerson(name="Alice").save()
        APerson(name="Bob").save()

        assert len([p.name for p in APerson.nodes]) == 2

    assert isinstance(transaction.last_bookmark, Bookmarks)
