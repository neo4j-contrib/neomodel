from test._async_compat import mark_sync_test

from pytest import raises

from neomodel import (
    IntegerProperty,
    RelationshipFrom,
    RelationshipTo,
    StringProperty,
    StructuredNode,
    UniqueIdProperty,
    config,
)
from neomodel._async_compat.util import Util
from neomodel.exceptions import DeflateError, UniqueProperty

config.AUTO_INSTALL_LABELS = True


class UniqueUser(StructuredNode):
    uid = UniqueIdProperty()
    name = StringProperty()
    age = IntegerProperty()


@mark_sync_test
def test_unique_id_property_batch():
    users = UniqueUser.create({"name": "bob", "age": 2}, {"name": "ben", "age": 3})

    assert users[0].uid != users[1].uid

    users = UniqueUser.get_or_create({"uid": users[0].uid}, {"name": "bill", "age": 4})

    assert users[0].name == "bob"
    assert users[1].uid


class Customer(StructuredNode):
    email = StringProperty(unique_index=True, required=True)
    age = IntegerProperty(index=True)


@mark_sync_test
def test_batch_create():
    users = Customer.create(
        {"email": "jim1@aol.com", "age": 11},
        {"email": "jim2@aol.com", "age": 7},
        {"email": "jim3@aol.com", "age": 9},
        {"email": "jim4@aol.com", "age": 7},
        {"email": "jim5@aol.com", "age": 99},
    )
    assert len(users) == 5
    assert users[0].age == 11
    assert users[1].age == 7
    assert users[1].email == "jim2@aol.com"
    assert Customer.nodes.get(email="jim1@aol.com")


@mark_sync_test
def test_batch_create_or_update():
    users = Customer.create_or_update(
        {"email": "merge1@aol.com", "age": 11},
        {"email": "merge2@aol.com"},
        {"email": "merge3@aol.com", "age": 1},
        {"email": "merge2@aol.com", "age": 2},
    )
    assert len(users) == 4
    assert users[1] == users[3]
    merge_1: Customer = Customer.nodes.get(email="merge1@aol.com")
    assert merge_1.age == 11

    more_users = Customer.create_or_update(
        {"email": "merge1@aol.com", "age": 22},
        {"email": "merge4@aol.com", "age": None},
    )
    assert len(more_users) == 2
    assert users[0] == more_users[0]
    merge_1 = Customer.nodes.get(email="merge1@aol.com")
    assert merge_1.age == 22


@mark_sync_test
def test_batch_validation():
    # test validation in batch create
    with raises(DeflateError):
        Customer.create(
            {"email": "jim1@aol.com", "age": "x"},
        )


@mark_sync_test
def test_batch_index_violation():
    for u in Customer.nodes:
        u.delete()

    users = Customer.create(
        {"email": "jim6@aol.com", "age": 3},
    )
    assert users
    with raises(UniqueProperty):
        Customer.create(
            {"email": "jim6@aol.com", "age": 3},
            {"email": "jim7@aol.com", "age": 5},
        )

    # not found
    if Util.is_async_code:
        assert not Customer.nodes.filter(email="jim7@aol.com").__bool__()
    else:
        assert not Customer.nodes.filter(email="jim7@aol.com")


class Dog(StructuredNode):
    name = StringProperty(required=True)
    owner = RelationshipTo("Person", "owner")


class Person(StructuredNode):
    name = StringProperty(unique_index=True)
    pets = RelationshipFrom("Dog", "owner")


@mark_sync_test
def test_get_or_create_with_rel():
    create_bob = Person.get_or_create({"name": "Bob"})
    bob = create_bob[0]
    bobs_gizmo = Dog.get_or_create({"name": "Gizmo"}, relationship=bob.pets)

    create_tim = Person.get_or_create({"name": "Tim"})
    tim = create_tim[0]
    tims_gizmo = Dog.get_or_create({"name": "Gizmo"}, relationship=tim.pets)

    # not the same gizmo
    assert bobs_gizmo[0] != tims_gizmo[0]
