import pytest
from neobolt.addressing import AddressError
from pytest import raises

from neomodel import db, StructuredNode, StringProperty, UniqueProperty


class APerson(StructuredNode):
    name = StringProperty(unique_index=True)


def test_rollback_and_commit_transaction():
    for p in APerson.nodes:
        p.delete()

    APerson(name='Roger').save()

    db.begin()
    APerson(name='Terry S').save()
    db.rollback()

    assert len(APerson.nodes) == 1

    db.begin()
    APerson(name='Terry S').save()
    db.commit()

    assert len(APerson.nodes) == 2


@db.transaction
def in_a_tx(*names):
    for n in names:
        APerson(name=n).save()


def test_transaction_decorator():
    for p in APerson.nodes:
        p.delete()

    # should work
    in_a_tx('Roger')
    assert True

    # should bail but raise correct error
    with raises(UniqueProperty):
        in_a_tx('Jim', 'Roger')

    assert 'Jim' not in [p.name for p in APerson.nodes]


def test_transaction_as_a_context():
    with db.transaction:
        APerson(name='Tim').save()

    assert APerson.nodes.filter(name='Tim')

    with raises(UniqueProperty):
        with db.transaction:
            APerson(name='Tim').save()


def test_query_inside_transaction():
    for p in APerson.nodes:
        p.delete()

    with db.transaction:
        APerson(name='Alice').save()
        APerson(name='Bob').save()

        assert len([p.name for p in APerson.nodes]) == 2


def test_set_connection_works():
    assert APerson(name='New guy 1').save()
    from socket import gaierror

    old_url = db.url
    with raises(ValueError):
        db.set_connection('bolt://user:password@6.6.6.6.6.6.6.6:7687')
        APerson(name='New guy 2').save()
    db.set_connection(old_url)
    # set connection back
    assert APerson(name='New guy 3').save()

@db.transaction.with_bookmark
def in_a_tx(*names):
    for n in names:
        APerson(name=n).save()


def test_bookmark_transaction_decorator(skip_neo4j_before_330):
    for p in APerson.nodes:
        p.delete()

    # should work
    result, bookmark = in_a_tx('Ruth', bookmarks=None)
    assert result is None
    assert isinstance(bookmark, str)

    # should bail but raise correct error
    with raises(UniqueProperty):
        in_a_tx('Jane', 'Ruth')

    assert 'Jane' not in [p.name for p in APerson.nodes]


def test_bookmark_transaction_as_a_context(skip_neo4j_before_330):
    with db.transaction as transaction:
        APerson(name='Tanya').save()
    assert isinstance(transaction.last_bookmark, str)

    assert APerson.nodes.filter(name='Tanya')

    with raises(UniqueProperty):
        with db.transaction as transaction:
            APerson(name='Tanya').save()
    assert not hasattr(transaction, 'last_bookmark')

@pytest.fixture
def spy_on_db_begin(monkeypatch):
    spy_calls = []
    original_begin = db.begin

    def begin_spy(*args, **kwargs):
        spy_calls.append((args, kwargs))
        return original_begin(*args, **kwargs)

    monkeypatch.setattr(db, 'begin', begin_spy)
    return spy_calls

def test_bookmark_passed_in_to_context(skip_neo4j_before_330, spy_on_db_begin):
    transaction = db.transaction
    with transaction:
        pass

    assert spy_on_db_begin[-1] == ((), { 'access_mode': None })
    last_bookmark = transaction.last_bookmark

    transaction.bookmarks = last_bookmark
    with transaction:
        pass
    assert spy_on_db_begin[-1] == ((), { 'access_mode': None, 'bookmarks': (last_bookmark,) })

    transaction.bookmarks = [last_bookmark]
    with transaction:
        pass
    assert spy_on_db_begin[-1] == ((), { 'access_mode': None, 'bookmarks': (last_bookmark,) })

def test_query_inside_bookmark_transaction(skip_neo4j_before_330):
    for p in APerson.nodes:
        p.delete()

    with db.transaction as transaction:
        APerson(name='Alice').save()
        APerson(name='Bob').save()

        assert len([p.name for p in APerson.nodes]) == 2

    assert isinstance(transaction.last_bookmark, str)
