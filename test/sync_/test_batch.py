from datetime import datetime
from test._async_compat import mark_sync_test
from zoneinfo import ZoneInfo

from pytest import raises

from neomodel import (
    DateTimeProperty,
    IntegerProperty,
    RelationshipFrom,
    RelationshipTo,
    StringProperty,
    StructuredNode,
    StructuredRel,
    UniqueIdProperty,
    db,
)
from neomodel._async_compat.util import Util
from neomodel.exceptions import DeflateError, UniqueProperty


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


class PetsRel(StructuredRel):
    since = DateTimeProperty()
    notes = StringProperty()


class DogWithRel(StructuredNode):
    name = StringProperty(required=True)
    owner = RelationshipTo("PersonWithRel", "OWNS", model=PetsRel)


class PersonWithRel(StructuredNode):
    name = StringProperty(unique_index=True)
    pets = RelationshipFrom("DogWithRel", "OWNS", model=PetsRel)


@mark_sync_test
def test_get_or_create_with_rel_props():
    """Test get_or_create with relationship properties"""
    create_bob = PersonWithRel.get_or_create({"name": "Bob"})
    bob = create_bob[0]

    since_date = datetime(2020, 1, 15, tzinfo=ZoneInfo("UTC"))

    dogs = DogWithRel.get_or_create(
        {"name": "Gizmo"},
        relationship=bob.pets,
        rel_props={"since": since_date, "notes": "Good boy!"},
    )
    assert len(dogs) == 1
    dog = dogs[0]
    assert dog.name == "Gizmo"

    owner_rels = dog.owner.all_relationships(bob)
    assert len(owner_rels) == 1
    rel = owner_rels[0]
    assert rel.since == since_date
    assert rel.notes == "Good boy!"


@mark_sync_test
def test_get_or_create_batch_with_rel_props():
    """Test get_or_create with multiple nodes, same relationship and rel_props"""
    alice = (PersonWithRel.get_or_create({"name": "Alice"}))[0]

    since_date = datetime(2021, 5, 20, tzinfo=ZoneInfo("UTC"))
    dogs = DogWithRel.get_or_create(
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
        owner_rels = dog.owner.all_relationships(alice)
        assert len(owner_rels) == 1
        rel = owner_rels[0]
        assert rel.since == since_date
        assert rel.notes == "Adopted together"


@mark_sync_test
def test_create_or_update_with_rel_props():
    """Test create_or_update with relationship properties"""
    charlie = (PersonWithRel.get_or_create({"name": "Charlie"}))[0]

    since_date = datetime(2019, 3, 10, tzinfo=ZoneInfo("UTC"))

    dogs = DogWithRel.create_or_update(
        {"name": "Spot"},
        relationship=charlie.pets,
        rel_props={"since": since_date, "notes": "First adoption"},
    )

    assert len(dogs) == 1
    dog = dogs[0]
    assert dog.name == "Spot"

    owner_rels = dog.owner.all_relationships(charlie)
    assert len(owner_rels) == 1
    rel = owner_rels[0]
    assert rel.since == since_date
    assert rel.notes == "First adoption"

    dogs2 = DogWithRel.create_or_update(
        {"name": "Spot"},
        relationship=charlie.pets,
        rel_props={"since": since_date, "notes": "Updated note"},
    )

    assert len(dogs2) == 1
    assert dogs2[0].element_id != dog.element_id


@mark_sync_test
def test_create_or_update_batch_with_rel_props():
    """Test create_or_update with multiple nodes and relationship properties"""
    diana = (PersonWithRel.get_or_create({"name": "Diana"}))[0]

    since_date = datetime(2022, 6, 15, tzinfo=ZoneInfo("UTC"))

    dogs = DogWithRel.create_or_update(
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
        owner_rels = dog.owner.all_relationships(diana)
        assert len(owner_rels) == 1
        rel = owner_rels[0]
        assert rel.since == since_date
        assert rel.notes == "Rescue dogs"


class NodeWithDefaultProp(StructuredNode):
    name = StringProperty(required=True)
    age = IntegerProperty(default=30)
    other_prop = StringProperty()


@mark_sync_test
def test_get_or_create_with_ignored_properties():
    node = NodeWithDefaultProp.get_or_create({"name": "Tania", "age": 20})
    assert node[0].name == "Tania"
    assert node[0].age == 20

    node = NodeWithDefaultProp.get_or_create({"name": "Tania"})
    assert node[0].name == "Tania"
    assert node[0].age == 20  # Tania was fetched and not created

    node = NodeWithDefaultProp.get_or_create({"name": "Tania", "age": 30})
    assert node[0].name == "Tania"
    assert node[0].age == 20  # Tania was fetched and not created


@mark_sync_test
def test_create_or_update_with_ignored_properties():
    node = NodeWithDefaultProp.create_or_update({"name": "Tania", "age": 20})
    assert node[0].name == "Tania"
    assert node[0].age == 20

    node = NodeWithDefaultProp.create_or_update(
        {"name": "Tania", "other_prop": "other"}
    )
    assert node[0].name == "Tania"
    assert (
        node[0].age == 20
    )  # Tania is still 20 even though default says she should be 30
    assert (
        node[0].other_prop == "other"
    )  # She does have a brand new other_prop, lucky her !

    node = NodeWithDefaultProp.create_or_update(
        {"name": "Tania", "age": 30, "other_prop": "other2"}
    )
    assert node[0].name == "Tania"
    assert node[0].age == 30  # Tania is now 30, congrats Tania !
    assert (
        node[0].other_prop == "other2"
    )  # Plus she has a new other_prop - as a birthday gift ?


@mark_sync_test
def test_lazy_mode():
    """Test lazy mode functionality."""

    node1 = (NodeWithDefaultProp.create({"name": "Tania", "age": 20}))[0]
    node = NodeWithDefaultProp.get_or_create({"name": "Tania", "age": 20}, lazy=True)
    if db.version_is_higher_than("5.0.0"):
        assert node[0] == node1.element_id
    else:
        assert node[0] == node1.id

    node = NodeWithDefaultProp.create_or_update({"name": "Tania", "age": 25}, lazy=True)
    if db.version_is_higher_than("5.0.0"):
        assert node[0] == node1.element_id
    else:
        assert node[0] == node1.id


class MergeKeyTestNode(StructuredNode):
    """Test node for merge key functionality tests."""

    name = StringProperty(required=True)
    email = StringProperty(required=True, unique_index=True)
    age = IntegerProperty()
    department = StringProperty()


class MergeKeyChildTestNode(MergeKeyTestNode):
    """Test node for merge key functionality tests with an extra label."""


@mark_sync_test
def test_default_merge_behavior():
    """Test default merge behavior using required properties."""

    # Create initial node
    node1 = (
        MergeKeyTestNode.create(
            {"name": "John", "email": "john@example.com", "age": 30}
        )
    )[0]

    # Update with same name and email (should update existing)
    nodes = MergeKeyTestNode.create_or_update(
        {"name": "John", "email": "john@example.com", "age": 31}
    )

    assert len(nodes) == 1
    assert nodes[0].element_id == node1.element_id
    assert nodes[0].age == 31

    # Verify the node was updated correctly
    assert nodes[0].name == "John"
    assert nodes[0].email == "john@example.com"
    assert nodes[0].age == 31


@mark_sync_test
def test_custom_merge_key_email():
    """Test custom merge key using email only."""

    # Create initial node
    node1 = (
        MergeKeyTestNode.create(
            {"name": "Jane", "email": "jane@example.com", "age": 25}
        )
    )[0]

    # Update with custom merge key (email only)
    nodes = MergeKeyTestNode.create_or_update(
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


@mark_sync_test
def test_merge_key_unspecified_label():
    """Test merge key with unspecified label."""

    # Create initial node
    node1 = (
        MergeKeyTestNode.create(
            {"name": "Jane", "email": "jane@example.com", "age": 25}
        )
    )[0]

    # Update with custom merge key (email only)
    nodes = MergeKeyTestNode.create_or_update(
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


@mark_sync_test
def test_get_or_create_with_merge_key():
    """Test get_or_create with custom merge key."""

    # Create initial node
    node1 = (
        MergeKeyTestNode.create(
            {"name": "Alice", "email": "alice@example.com", "age": 28}
        )
    )[0]

    # Use get_or_create with custom merge key
    nodes = MergeKeyTestNode.get_or_create(
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


@mark_sync_test
def test_merge_key_create_new_node():
    """Test that merge key creates new node when no match is found."""

    # Create node with merge key that won't match anything
    nodes = MergeKeyTestNode.create_or_update(
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


@mark_sync_test
def test_get_or_create_with_different_label():
    """Test merge key with different label specification."""

    # Create initial node
    node1 = (
        MergeKeyTestNode.create({"name": "Eve", "email": "eve@example.com", "age": 27})
    )[0]
    node2 = (
        MergeKeyChildTestNode.create(
            {"name": "Eve Child", "email": "evechild@example.com", "age": 27}
        )
    )[0]

    # Use merge key with explicit label - child one
    nodes = MergeKeyTestNode.get_or_create(
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
    nodes = MergeKeyTestNode.get_or_create(
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


@mark_sync_test
def test_multiple_merge_operations():
    """Test multiple merge operations with different keys."""

    # Create initial nodes
    node1 = (
        MergeKeyTestNode.create(
            {"name": "Frank", "email": "frank@example.com", "age": 45}
        )
    )[0]
    node2 = (
        MergeKeyTestNode.create(
            {"name": "Grace", "email": "grace@example.com", "age": 38}
        )
    )[0]

    # Update Frank by email
    nodes1 = MergeKeyTestNode.create_or_update(
        {"name": "Franklin", "email": "frank@example.com", "age": 46},
        merge_by={"label": "MergeKeyTestNode", "keys": ["email"]},
    )

    # Update Grace by name
    nodes2 = MergeKeyTestNode.create_or_update(
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


@mark_sync_test
def test_merge_key_lazy_mode():
    """Test merge key functionality with lazy mode."""

    # Create initial node
    node1 = (
        MergeKeyTestNode.create(
            {"name": "Diana", "email": "diana@example.com", "age": 32}
        )
    )[0]

    # Test with lazy mode
    nodes = MergeKeyTestNode.create_or_update(
        {"name": "Diana Prince", "email": "diana@example.com", "age": 33},
        merge_by={"label": "MergeKeyTestNode", "keys": ["email"]},
        lazy=True,
    )

    assert len(nodes) == 1
    # In lazy mode, we should get the element_id back
    if db.version_is_higher_than("5.0.0"):
        assert nodes[0] == node1.element_id
    else:
        assert nodes[0] == node1.id


@mark_sync_test
def test_merge_key_with_multiple_properties():
    """Test merge key with a property that has multiple values."""

    # Create initial node
    node1 = (
        MergeKeyTestNode.create(
            {
                "name": "Multi",
                "email": "multi@example.com",
                "age": 25,
                "department": "Engineering",
            }
        )
    )[0]

    # Update with different department but same email
    nodes = MergeKeyTestNode.create_or_update(
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


@mark_sync_test
def test_merge_key_with_get_or_create_multiple_keys():
    """Test merge key for get_or_create with multiple keys."""

    # Create initial node
    node1 = (
        MergeKeyTestNode.create(
            {
                "name": "Charlie",
                "email": "charlie@example.com",
                "age": 35,
            }
        )
    )[0]

    # Use get_or_create with multiple keys
    nodes = MergeKeyTestNode.get_or_create(
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
    nodes2 = MergeKeyTestNode.get_or_create(
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


@mark_sync_test
def test_merge_key_with_create_or_update_multiple_keys():
    """Test merge key for create_or_update with multiple keys."""

    # Create initial node
    node1 = (
        MergeKeyTestNode.create(
            {
                "name": "John",
                "email": "john@example.com",
                "age": 30,
                "department": "Engineering",
            }
        )
    )[0]

    # Update with same name and email (both keys match)
    nodes = MergeKeyTestNode.create_or_update(
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
    nodes2 = MergeKeyTestNode.create_or_update(
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
