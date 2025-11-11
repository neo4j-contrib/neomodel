from datetime import UTC, datetime

from pytest import raises

from neomodel import (
    AsyncRelationshipFrom,
    AsyncRelationshipTo,
    AsyncStructuredNode,
    AsyncStructuredRel,
    DateTimeProperty,
    IntegerProperty,
    StringProperty,
    UniqueIdProperty,
    config,
)
from neomodel._async_compat.util import AsyncUtil
from neomodel.exceptions import DeflateError, UniqueProperty
from test._async_compat import mark_async_test

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


class PetsRel(AsyncStructuredRel):
    since = DateTimeProperty()
    notes = StringProperty()


class DogWithRel(AsyncStructuredNode):
    name = StringProperty(required=True)
    owner = AsyncRelationshipTo("PersonWithRel", "OWNS", model=PetsRel)


class PersonWithRel(AsyncStructuredNode):
    name = StringProperty(unique_index=True)
    pets = AsyncRelationshipFrom("DogWithRel", "OWNS", model=PetsRel)


@mark_async_test
async def test_get_or_create_with_rel_props():
    """Test get_or_create with relationship properties"""
    create_bob = await PersonWithRel.get_or_create({"name": "Bob"})
    bob = create_bob[0]

    since_date = datetime(2020, 1, 15, tzinfo=UTC)

    dogs = await DogWithRel.get_or_create(
        {"name": "Gizmo"},
        relationship=bob.pets,
        rel_props={"since": since_date, "notes": "Good boy!"},
    )
    assert len(dogs) == 1
    dog = dogs[0]
    assert dog.name == "Gizmo"

    owner_rels = await dog.owner.all_relationships(bob)
    assert len(owner_rels) == 1
    rel = owner_rels[0]
    assert rel.since == since_date
    assert rel.notes == "Good boy!"


@mark_async_test
async def test_get_or_create_batch_with_rel_props():
    """Test get_or_create with multiple nodes, same relationship and rel_props"""
    alice = (await PersonWithRel.get_or_create({"name": "Alice"}))[0]

    since_date = datetime(2021, 5, 20, tzinfo=UTC)
    dogs = await DogWithRel.get_or_create(
        {"name": "Rex"},
        {"name": "Max"},
        {"name": "Luna"},
        relationship=alice.pets,
        rel_props={"since": since_date, "notes": "Adopted together"},
    )

    assert len(dogs) == 3
    assert dogs[0].name == "Rex"
    assert dogs[1].name == "Max"
    assert dogs[2].name == "Luna"

    for dog in dogs:
        owner_rels = await dog.owner.all_relationships(alice)
        assert len(owner_rels) == 1
        rel = owner_rels[0]
        assert rel.since == since_date
        assert rel.notes == "Adopted together"


@mark_async_test
async def test_create_or_update_with_rel_props():
    """Test create_or_update with relationship properties"""
    charlie = (await PersonWithRel.get_or_create({"name": "Charlie"}))[0]

    since_date = datetime(2019, 3, 10, tzinfo=UTC)

    dogs = await DogWithRel.create_or_update(
        {"name": "Spot"},
        relationship=charlie.pets,
        rel_props={"since": since_date, "notes": "First adoption"},
    )

    assert len(dogs) == 1
    dog = dogs[0]
    assert dog.name == "Spot"

    owner_rels = await dog.owner.all_relationships(charlie)
    assert len(owner_rels) == 1
    rel = owner_rels[0]
    assert rel.since == since_date
    assert rel.notes == "First adoption"

    dogs2 = await DogWithRel.create_or_update(
        {"name": "Spot"},
        relationship=charlie.pets,
        rel_props={"since": since_date, "notes": "Updated note"},
    )

    assert len(dogs2) == 1
    assert dogs2[0].element_id != dog.element_id


@mark_async_test
async def test_create_or_update_batch_with_rel_props():
    """Test create_or_update with multiple nodes and relationship properties"""
    diana = (await PersonWithRel.get_or_create({"name": "Diana"}))[0]

    since_date = datetime(2022, 6, 15, tzinfo=UTC)

    dogs = await DogWithRel.create_or_update(
        {"name": "Bella"},
        {"name": "Charlie"},
        {"name": "Daisy"},
        relationship=diana.pets,
        rel_props={"since": since_date, "notes": "Rescue dogs"},
    )

    assert len(dogs) == 3
    assert dogs[0].name == "Bella"
    assert dogs[1].name == "Charlie"
    assert dogs[2].name == "Daisy"

    for dog in dogs:
        owner_rels = await dog.owner.all_relationships(diana)
        assert len(owner_rels) == 1
        rel = owner_rels[0]
        assert rel.since == since_date
        assert rel.notes == "Rescue dogs"
