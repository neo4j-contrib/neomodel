from test._async_compat import mark_async_test

from pytest import raises

from neomodel import (
    AsyncRelationshipFrom,
    AsyncRelationshipTo,
    AsyncStructuredNode,
    IntegerProperty,
    StringProperty,
    UniqueIdProperty,
    config,
)
from neomodel._async_compat.util import AsyncUtil
from neomodel.exceptions import DeflateError, UniqueProperty

config.AUTO_INSTALL_LABELS = True


class UniqueUser(AsyncStructuredNode):
    uid = UniqueIdProperty()
    name = StringProperty()
    age = IntegerProperty()


@mark_async_test
async def test_unique_id_property_batch():
    users = await UniqueUser.create(
        {"name": "bob", "age": 2}, {"name": "ben", "age": 3}
    )

    assert users[0].uid != users[1].uid

    users = await UniqueUser.get_or_create(
        {"uid": users[0].uid}, {"name": "bill", "age": 4}
    )

    assert users[0].name == "bob"
    assert users[1].uid


class Customer(AsyncStructuredNode):
    email = StringProperty(unique_index=True, required=True)
    age = IntegerProperty(index=True)


@mark_async_test
async def test_batch_create():
    users = await Customer.create(
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
    assert await Customer.nodes.get(email="jim1@aol.com")


@mark_async_test
async def test_batch_create_or_update():
    users = await Customer.create_or_update(
        {"email": "merge1@aol.com", "age": 11},
        {"email": "merge2@aol.com"},
        {"email": "merge3@aol.com", "age": 1},
        {"email": "merge2@aol.com", "age": 2},
    )
    assert len(users) == 4
    assert users[1] == users[3]
    merge_1: Customer = await Customer.nodes.get(email="merge1@aol.com")
    assert merge_1.age == 11

    more_users = await Customer.create_or_update(
        {"email": "merge1@aol.com", "age": 22},
        {"email": "merge4@aol.com", "age": None},
    )
    assert len(more_users) == 2
    assert users[0] == more_users[0]
    merge_1 = await Customer.nodes.get(email="merge1@aol.com")
    assert merge_1.age == 22


@mark_async_test
async def test_batch_validation():
    # test validation in batch create
    with raises(DeflateError):
        await Customer.create(
            {"email": "jim1@aol.com", "age": "x"},
        )


@mark_async_test
async def test_batch_index_violation():
    for u in await Customer.nodes:
        await u.delete()

    users = await Customer.create(
        {"email": "jim6@aol.com", "age": 3},
    )
    assert users
    with raises(UniqueProperty):
        await Customer.create(
            {"email": "jim6@aol.com", "age": 3},
            {"email": "jim7@aol.com", "age": 5},
        )

    # not found
    if AsyncUtil.is_async_code:
        assert not await Customer.nodes.filter(email="jim7@aol.com").check_bool()
    else:
        assert not Customer.nodes.filter(email="jim7@aol.com")


class Dog(AsyncStructuredNode):
    name = StringProperty(required=True)
    owner = AsyncRelationshipTo("Person", "owner")


class Person(AsyncStructuredNode):
    name = StringProperty(unique_index=True)
    pets = AsyncRelationshipFrom("Dog", "owner")


@mark_async_test
async def test_get_or_create_with_rel():
    create_bob = await Person.get_or_create({"name": "Bob"})
    bob = create_bob[0]
    bobs_gizmo = await Dog.get_or_create({"name": "Gizmo"}, relationship=bob.pets)

    create_tim = await Person.get_or_create({"name": "Tim"})
    tim = create_tim[0]
    tims_gizmo = await Dog.get_or_create({"name": "Gizmo"}, relationship=tim.pets)

    # not the same gizmo
    assert bobs_gizmo[0] != tims_gizmo[0]
