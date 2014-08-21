from neomodel import (StructuredNode, StringProperty, IntegerProperty)
from neomodel.exception import UniqueProperty, DeflateError


class Customer(StructuredNode):
    email = StringProperty(unique_index=True, required=True)
    age = IntegerProperty(index=True)


def test_batch_create():
    users = Customer.create(
            {'email': 'jim1@aol.com', 'age': 11},
            {'email': 'jim2@aol.com', 'age': 7},
            {'email': 'jim3@aol.com', 'age': 9},
            {'email': 'jim4@aol.com', 'age': 7},
            {'email': 'jim5@aol.com', 'age': 99},
    )
    assert len(users) == 5
    assert users[0].age == 11
    assert users[1].age == 7
    assert users[1].email == 'jim2@aol.com'
    assert Customer.nodes.get(email='jim1@aol.com')


def test_batch_validation():
    # test validation in batch create
    try:
        Customer.create(
            {'email': 'jim1@aol.com', 'age': 'x'},
        )
    except DeflateError:
        assert True
    else:
        assert False


def test_batch_index_violation():
    for u in Customer.nodes.all():
        u.delete()

    users = Customer.create(
        {'email': 'jim6@aol.com', 'age': 3},
    )
    assert users
    try:
        Customer.create(
            {'email': 'jim6@aol.com', 'age': 3},
            {'email': 'jim7@aol.com', 'age': 5},
        )
    except UniqueProperty:
        assert True
    else:
        assert False

    # not found
    assert not Customer.nodes.filter(email='jim7@aol.com')
