from neo4j.addressing import AddressError
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
    assert APerson(name='New guy').save()
    from socket import gaierror

    old_url = db.url
    with raises(AddressError):
        db.set_connection('bolt://user:password@nowhere:7687')
    db.set_connection(old_url)
    # set connection back
    assert APerson(name='New guy2').save()
