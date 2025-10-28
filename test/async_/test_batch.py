from test._async_compat import mark_async_test

from pytest import raises

from neomodel import (
    AsyncRelationshipFrom,
    AsyncRelationshipTo,
    AsyncStructuredNode,
    IntegerProperty,
    StringProperty,
    UniqueIdProperty,
    adb,
)
from neomodel._async_compat.util import AsyncUtil
from neomodel.exceptions import DeflateError, UniqueProperty


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


class NodeWithDefaultProp(AsyncStructuredNode):
    name = StringProperty(required=True)
    age = IntegerProperty(default=30)
    other_prop = StringProperty()


@mark_async_test
async def test_get_or_create_with_ignored_properties():
    node = await NodeWithDefaultProp.get_or_create({"name": "Tania", "age": 20})
    assert node[0].name == "Tania"
    assert node[0].age == 20

    node = await NodeWithDefaultProp.get_or_create({"name": "Tania"})
    assert node[0].name == "Tania"
    assert node[0].age == 20  # Tania was fetched and not created

    node = await NodeWithDefaultProp.get_or_create({"name": "Tania", "age": 30})
    assert node[0].name == "Tania"
    assert node[0].age == 20  # Tania was fetched and not created


@mark_async_test
async def test_create_or_update_with_ignored_properties():
    node = await NodeWithDefaultProp.create_or_update({"name": "Tania", "age": 20})
    assert node[0].name == "Tania"
    assert node[0].age == 20

    node = await NodeWithDefaultProp.create_or_update(
        {"name": "Tania", "other_prop": "other"}
    )
    assert node[0].name == "Tania"
    assert (
        node[0].age == 20
    )  # Tania is still 20 even though default says she should be 30
    assert (
        node[0].other_prop == "other"
    )  # She does have a brand new other_prop, lucky her !

    node = await NodeWithDefaultProp.create_or_update(
        {"name": "Tania", "age": 30, "other_prop": "other2"}
    )
    assert node[0].name == "Tania"
    assert node[0].age == 30  # Tania is now 30, congrats Tania !
    assert (
        node[0].other_prop == "other2"
    )  # Plus she has a new other_prop - as a birthday gift ?


@mark_async_test
async def test_lazy_mode():
    """Test lazy mode functionality."""

    node1 = (await NodeWithDefaultProp.create({"name": "Tania", "age": 20}))[0]
    node = await NodeWithDefaultProp.get_or_create(
        {"name": "Tania", "age": 20}, lazy=True
    )
    if await adb.version_is_higher_than("5.0.0"):
        assert node[0] == node1.element_id
    else:
        assert node[0] == node1.id

    node = await NodeWithDefaultProp.create_or_update(
        {"name": "Tania", "age": 25}, lazy=True
    )
    if await adb.version_is_higher_than("5.0.0"):
        assert node[0] == node1.element_id
    else:
        assert node[0] == node1.id


class MergeKeyTestNode(AsyncStructuredNode):
    """Test node for merge key functionality tests."""

    name = StringProperty(required=True)
    email = StringProperty(required=True, unique_index=True)
    age = IntegerProperty()
    department = StringProperty()


class MergeKeyChildTestNode(MergeKeyTestNode):
    """Test node for merge key functionality tests with an extra label."""


@mark_async_test
async def test_default_merge_behavior():
    """Test default merge behavior using required properties."""

    # Create initial node
    node1 = (
        await MergeKeyTestNode.create(
            {"name": "John", "email": "john@example.com", "age": 30}
        )
    )[0]

    # Update with same name and email (should update existing)
    nodes = await MergeKeyTestNode.create_or_update(
        {"name": "John", "email": "john@example.com", "age": 31}
    )

    assert len(nodes) == 1
    assert nodes[0].element_id == node1.element_id
    assert nodes[0].age == 31

    # Verify the node was updated correctly
    assert nodes[0].name == "John"
    assert nodes[0].email == "john@example.com"
    assert nodes[0].age == 31


@mark_async_test
async def test_custom_merge_key_email():
    """Test custom merge key using email only."""

    # Create initial node
    node1 = (
        await MergeKeyTestNode.create(
            {"name": "Jane", "email": "jane@example.com", "age": 25}
        )
    )[0]

    # Update with custom merge key (email only)
    nodes = await MergeKeyTestNode.create_or_update(
        {
            "name": "Jane Doe",  # Different name
            "email": "jane@example.com",  # Same email
            "age": 26,
        },
        merge_by={"label": "MergeKeyTestNode", "keys": ["email"]},
    )

    assert len(nodes) == 1
    assert nodes[0].element_id == node1.element_id  # Node should be the same
    assert nodes[0].name == "Jane Doe"  # Name should be updated
    assert nodes[0].age == 26  # Age should be updated


@mark_async_test
async def test_merge_key_unspecified_label():
    """Test merge key with unspecified label."""

    # Create initial node
    node1 = (
        await MergeKeyTestNode.create(
            {"name": "Jane", "email": "jane@example.com", "age": 25}
        )
    )[0]

    # Update with custom merge key (email only)
    nodes = await MergeKeyTestNode.create_or_update(
        {
            "name": "Jane Doe",  # Different name
            "email": "jane@example.com",  # Same email
            "age": 26,
        },
        merge_by={"keys": ["email"]},
    )

    assert len(nodes) == 1
    assert nodes[0].element_id == node1.element_id  # Node should be the same
    assert nodes[0].name == "Jane Doe"  # Name should be updated
    assert nodes[0].age == 26  # Age should be updated


@mark_async_test
async def test_get_or_create_with_merge_key():
    """Test get_or_create with custom merge key."""

    # Create initial node
    node1 = (
        await MergeKeyTestNode.create(
            {"name": "Alice", "email": "alice@example.com", "age": 28}
        )
    )[0]

    # Use get_or_create with custom merge key
    nodes = await MergeKeyTestNode.get_or_create(
        {
            "name": "Alice Smith",  # Different name
            "email": "alice@example.com",  # Same email
            "age": 29,
        },
        merge_by={"label": "MergeKeyTestNode", "keys": ["email"]},
    )

    assert len(nodes) == 1
    assert nodes[0].element_id == node1.element_id  # Node was fetched and not created
    assert nodes[0].name == "Alice"  # Name should be the same
    assert nodes[0].age == 28


@mark_async_test
async def test_merge_key_create_new_node():
    """Test that merge key creates new node when no match is found."""

    # Create node with merge key that won't match anything
    nodes = await MergeKeyTestNode.create_or_update(
        {"name": "New User", "email": "new@example.com", "age": 30},
        merge_by={"label": "MergeKeyTestNode", "keys": ["email"]},
    )

    assert len(nodes) == 1
    assert nodes[0].name == "New User"
    assert nodes[0].email == "new@example.com"
    assert nodes[0].age == 30

    # Verify the node was created correctly
    assert nodes[0].name == "New User"
    assert nodes[0].email == "new@example.com"
    assert nodes[0].age == 30


@mark_async_test
async def test_get_or_create_with_different_label():
    """Test merge key with different label specification."""

    # Create initial node
    node1 = (
        await MergeKeyTestNode.create(
            {"name": "Eve", "email": "eve@example.com", "age": 27}
        )
    )[0]
    node2 = (
        await MergeKeyChildTestNode.create(
            {"name": "Eve Child", "email": "evechild@example.com", "age": 27}
        )
    )[0]

    # Use merge key with explicit label - child one
    nodes = await MergeKeyTestNode.get_or_create(
        {
            "name": "Eve Child",  # Different name
            "email": "evechild@example.com",  # Same email
            "age": 27,
        },
        merge_by={"label": "MergeKeyChildTestNode", "keys": ["age"]},
    )

    assert len(nodes) == 1  # Only the node with child label
    assert nodes[0].element_id == node2.element_id  # Node was fetched and not created
    assert nodes[0].name == "Eve Child"

    # Use merge key with explicit label - parent one
    nodes = await MergeKeyTestNode.get_or_create(
        {
            "name": "Eve Child",  # Different name
            "email": "evechild@example.com",  # Same email
            "age": 27,
        },
        merge_by={"label": "MergeKeyTestNode", "keys": ["age"]},
    )

    assert len(nodes) == 2  # Both nodes were fetched
    element_ids = [node.element_id for node in nodes]
    assert node1.element_id in element_ids
    assert node2.element_id in element_ids


@mark_async_test
async def test_multiple_merge_operations():
    """Test multiple merge operations with different keys."""

    # Create initial nodes
    node1 = (
        await MergeKeyTestNode.create(
            {"name": "Frank", "email": "frank@example.com", "age": 45}
        )
    )[0]
    node2 = (
        await MergeKeyTestNode.create(
            {"name": "Grace", "email": "grace@example.com", "age": 38}
        )
    )[0]

    # Update Frank by email
    nodes1 = await MergeKeyTestNode.create_or_update(
        {"name": "Franklin", "email": "frank@example.com", "age": 46},
        merge_by={"label": "MergeKeyTestNode", "keys": ["email"]},
    )

    # Update Grace by name
    nodes2 = await MergeKeyTestNode.create_or_update(
        {"name": "Grace", "email": "grace.new@example.com", "age": 39},
        merge_by={"label": "MergeKeyTestNode", "keys": ["name"]},
    )

    assert len(nodes1) == 1
    assert len(nodes2) == 1
    assert nodes1[0].element_id == node1.element_id
    assert nodes2[0].element_id == node2.element_id
    assert nodes1[0].name == "Franklin"
    assert nodes2[0].email == "grace.new@example.com"

    # Verify both nodes were updated correctly
    assert nodes1[0].name == "Franklin"
    assert nodes2[0].email == "grace.new@example.com"


@mark_async_test
async def test_merge_key_lazy_mode():
    """Test merge key functionality with lazy mode."""

    # Create initial node
    node1 = (
        await MergeKeyTestNode.create(
            {"name": "Diana", "email": "diana@example.com", "age": 32}
        )
    )[0]

    # Test with lazy mode
    nodes = await MergeKeyTestNode.create_or_update(
        {"name": "Diana Prince", "email": "diana@example.com", "age": 33},
        merge_by={"label": "MergeKeyTestNode", "keys": ["email"]},
        lazy=True,
    )

    assert len(nodes) == 1
    # In lazy mode, we should get the element_id back
    if await adb.version_is_higher_than("5.0.0"):
        assert nodes[0] == node1.element_id
    else:
        assert nodes[0] == node1.id


@mark_async_test
async def test_merge_key_with_multiple_properties():
    """Test merge key with a property that has multiple values."""

    # Create initial node
    node1 = (
        await MergeKeyTestNode.create(
            {
                "name": "Multi",
                "email": "multi@example.com",
                "age": 25,
                "department": "Engineering",
            }
        )
    )[0]

    # Update with different department but same email
    nodes = await MergeKeyTestNode.create_or_update(
        {
            "name": "Multi Updated",
            "email": "multi@example.com",
            "age": 26,
            "department": "Management",
        },
        merge_by={"label": "MergeKeyTestNode", "keys": ["email"]},
    )

    assert len(nodes) == 1
    assert nodes[0].element_id == node1.element_id  # Node should be the same
    assert nodes[0].name == "Multi Updated"
    assert nodes[0].department == "Management"
    assert nodes[0].age == 26


@mark_async_test
async def test_merge_key_with_get_or_create_multiple_keys():
    """Test merge key for get_or_create with multiple keys."""

    # Create initial node
    node1 = (
        await MergeKeyTestNode.create(
            {
                "name": "Charlie",
                "email": "charlie@example.com",
                "age": 35,
            }
        )
    )[0]

    # Use get_or_create with multiple keys
    nodes = await MergeKeyTestNode.get_or_create(
        {
            "name": "Charlie",
            "email": "charlie@example.com",
            "age": 36,
        },
        merge_by={"label": "MergeKeyTestNode", "keys": ["name", "email"]},
    )

    assert len(nodes) == 1
    assert nodes[0].element_id == node1.element_id
    assert nodes[0].age == 35

    # Try to get_or_create with different keys (should create new)
    nodes2 = await MergeKeyTestNode.get_or_create(
        {
            "name": "Charlie",
            "email": "charlie.doe@example.com",  # Different email
            "age": 37,
        },
        merge_by={"label": "MergeKeyTestNode", "keys": ["name", "email"]},
    )

    assert len(nodes2) == 1
    assert nodes2[0].element_id != node1.element_id
    assert nodes2[0].name == "Charlie"
    assert nodes2[0].email == "charlie.doe@example.com"


@mark_async_test
async def test_merge_key_with_create_or_update_multiple_keys():
    """Test merge key for create_or_update with multiple keys."""

    # Create initial node
    node1 = (
        await MergeKeyTestNode.create(
            {
                "name": "John",
                "email": "john@example.com",
                "age": 30,
                "department": "Engineering",
            }
        )
    )[0]

    # Update with same name and email (both keys match)
    nodes = await MergeKeyTestNode.create_or_update(
        {
            "name": "John",
            "email": "john@example.com",
            "age": 31,
            "department": "Management",
        },
        merge_by={"label": "MergeKeyTestNode", "keys": ["name", "email"]},
    )

    assert len(nodes) == 1
    assert nodes[0].element_id == node1.element_id
    assert nodes[0].age == 31
    assert nodes[0].department == "Management"

    # Test with only one key matching (should create new node)
    nodes2 = await MergeKeyTestNode.create_or_update(
        {
            "name": "John",
            "email": "john.doe@example.com",  # Different email
            "age": 32,
            "department": "Sales",
        },
        merge_by={"label": "MergeKeyTestNode", "keys": ["name", "email"]},
    )

    assert len(nodes2) == 1
    assert nodes2[0].element_id != node1.element_id  # Should be a new node
    assert nodes2[0].name == "John"
    assert nodes2[0].email == "john.doe@example.com"
