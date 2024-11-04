from test._async_compat import mark_async_test

import pytest
from neo4j.api import Bookmarks
from neo4j.exceptions import ClientError, TransactionError
from pytest import raises

from neomodel import AsyncStructuredNode, StringProperty, UniqueProperty, adb


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
async def double_transaction():
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
    assert isinstance(transaction.last_bookmark, Bookmarks)

    assert await APerson.nodes.filter(name="Tanya")

    with raises(UniqueProperty):
        async with adb.transaction as transaction:
            await APerson(name="Tanya").save()
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


@mark_async_test
async def test_bookmark_passed_in_to_context(spy_on_db_begin):
    transaction = adb.transaction
    async with transaction:
        pass

    assert (spy_on_db_begin)[-1] == ((), {"access_mode": None, "bookmarks": None})
    last_bookmark = transaction.last_bookmark

    transaction.bookmarks = last_bookmark
    async with transaction:
        pass
    assert spy_on_db_begin[-1] == (
        (),
        {"access_mode": None, "bookmarks": last_bookmark},
    )


@mark_async_test
async def test_query_inside_bookmark_transaction():
    async with adb.transaction as transaction:
        await APerson(name="Alice").save()
        await APerson(name="Bob").save()

        assert len([p.name for p in await APerson.nodes]) == 2

    assert isinstance(transaction.last_bookmark, Bookmarks)
