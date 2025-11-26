=====================
Batch node operations
=====================

All batch operations can be executed with one or more nodes.

create()
--------
Note that batch create is a relic of the Neo4j REST API.
With the adoption of Bolt by neomodel, it exists for convenience and compatibility 
and a CREATE query is issued for each `dict` provided.

Create multiple nodes at once in a single transaction::

    with db.transaction:
        people = Person.create(
            {'name': 'Tim', 'age': 83},
            {'name': 'Bob', 'age': 23},
            {'name': 'Jill', 'age': 34},
        )


create_or_update()
------------------
Atomically create or update nodes in a single operation.
The **required** and **unique** properties are used as keys to match nodes,
all other properties being used only on the resulting write operation.
For example::

    class Person(StructuredNode):
        name = StringProperty(required=True)
        age = IntegerProperty()

    people = Person.create_or_update(
        {'name': 'Tim', 'age': 83}, # created
        {'name': 'Bob', 'age': 23}, # created
        {'name': 'Jill', 'age': 34}, # created
    )

    more_people = Person.create_or_update(
        {'name': 'Tim', 'age': 73}, # updated
        {'name': 'Bob', 'age': 35}, # updated
        {'name': 'Jane', 'age': 24}, # created
    )

Custom Merge Keys
~~~~~~~~~~~~~~~~~
By default, neomodel uses all required properties as merge keys.
However, you can specify custom merge criteria using the ``merge_by`` parameter::

    class User(StructuredNode):
        username = StringProperty(required=True)
        email = StringProperty(required=True)
        full_name = StringProperty()
        age = IntegerProperty()

    # Default behavior (merge by username + email)
    users = User.create_or_update({
        'username': 'johndoe',
        'email': 'john@example.com',
        'age': 30
    })

    # Custom merge by email only
    users = User.create_or_update({
        'username': 'johndoe',
        'email': 'john@example.com',
        'age': 31
    }, merge_by={'keys': ['email']})

    # Custom merge by username only
    users = User.create_or_update({
        'username': 'johndoe',
        'email': 'john.doe@newcompany.com',
        'age': 32
    }, merge_by={'label': 'User', 'keys': ['username']})

The ``merge_by`` parameter accepts a dictionary with:
- ``label``: The Neo4j label to match against (optional, defaults to the node's inherited labels)
- ``keys``: The property name(s) to use as the merge key(s).

This is particularly useful when you want to merge nodes based on specific properties
rather than all required properties, or when you need to merge based on properties
that are not required.

Examples of different merge key configurations::

    # Single key (string)
    users = User.create_or_update({
        'username': 'johndoe',
        'email': 'john@example.com',
        'age': 30
    }, merge_by={'keys': ['email']})

    # Multiple keys (list)
    users = User.create_or_update({
        'username': 'johndoe',
        'email': 'john@example.com',
        'age': 30
    }, merge_by={'label': 'User', 'keys': ['username', 'email']})

    # Multiple keys with different label
    users = User.create_or_update({
        'username': 'johndoe',
        'email': 'john@example.com',
        'age': 30
    }, merge_by={'label': 'Person', 'keys': ['email', 'age']}) # For when your node has multiple labels

Only explicitly provided properties will be updated on the node in all other cases::
    class NodeWithDefaultProp(AsyncStructuredNode):
        name = StringProperty(required=True)
        age = IntegerProperty(default=30)
        other_prop = StringProperty()

    node = await NodeWithDefaultProp.create_or_update({"name": "Tania", "age": 20})
    assert node[0].name == "Tania"
    assert node[0].age == 20

    node = await MultiRequiredPropNode.create_or_update(
        {"name": "Tania", "other_prop": "other"}
    )
    assert node[0].name == "Tania"
    assert (
        node[0].age == 20
    )  # Tania is still 20 even though default says she should be 30
    assert (
        node[0].other_prop == "other"
    )  # She does have a brand new other_prop, lucky her !


However, if fields used as keys have default values, those default values will be used if the property is omitted in your call.
This means that when using `UniqueIdProperty`, which is both unique and has a default value, if you do not pass it explicitly,
it will generate a new (random) value for it, and thus create a new node instead of updating an existing one::

    class UniquePerson(StructuredNode):
        uid = UniqueIdProperty()
        name = StringProperty(required=True)

    unique_person = UniquePerson.create_or_update({"name": "Tim"}) # created
    unique_person = UniquePerson.create_or_update({"name": "Tim"}) # created again with a new uid

.. attention::
    This has been raised as an [issue in GitHub](https://github.com/neo4j-contrib/neomodel/issues/807).
    While it is not a bug in itself, it is a deviation from the expected behavior of the function, and thus may be unexpected.
    Therefore, an idea would be to refactor the batch mechanism to allow users to specify which properties are used as keys to match nodes.


Relationships and Relationship Properties
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The ``create_or_update()`` method also supports the ``relationship`` parameter to match nodes within a specific relationship context,
and the ``rel_props`` parameter to set properties on the relationship::

    from datetime import datetime, UTC

    class PetsRel(StructuredRel):
        since = DateTimeProperty()
        notes = StringProperty()

    class Dog(StructuredNode):
        name = StringProperty(required=True)
        owner = RelationshipTo('Person', 'OWNS', model=PetsRel)

    class Person(StructuredNode):
        name = StringProperty(unique_index=True)
        pets = RelationshipFrom('Dog', 'OWNS', model=PetsRel)

    charlie = Person.get_or_create({"name": "Charlie"})[0]
    since_date = datetime(2019, 3, 10, tzinfo=UTC)

    dogs = Dog.create_or_update(
        {"name": "Spot"},
        relationship=charlie.pets,
        rel_props={"since": since_date, "notes": "First adoption"},
    )

You can also create or update multiple nodes in a batch with the same relationship and relationship properties::

    diana = Person.get_or_create({"name": "Diana"})[0]
    since_date = datetime(2022, 6, 15, tzinfo=UTC)

    dogs = Dog.create_or_update(
        {"name": "Bella"},
        {"name": "Charlie"},
        {"name": "Daisy"},
        relationship=diana.pets,
        rel_props={"since": since_date, "notes": "Rescue dogs"},
    )

.. note::
    When using ``create_or_update()`` with a relationship, if a node is matched and updated, a new relationship
    will be created with the provided ``rel_props``. The old relationship (if it existed) will remain, and you may
    end up with multiple relationships between the same nodes.


get_or_create()
---------------
Atomically get or create nodes in a single operation.
For example::

    people = Person.get_or_create(
        {'name': 'Tim'}, # created
        {'name': 'Bob'}, # created
    )

    people_with_jill = Person.get_or_create(
        {'name': 'Tim'}, # fetched
        {'name': 'Bob'}, # fetched
        {'name': 'Jill'}, # created
    )
    # are same nodes
    assert people[0] == people_with_jill[0]
    assert people[1] == people_with_jill[1]

The **required** and **unique** properties are used as keys to match nodes,
all other properties being used only when a new node is created.
For example::
    class Person(StructuredNode):
        name = StringProperty(required=True)
        age = IntegerProperty()

    node = await Person.get_or_create({"name": "Tania", "age": 20})
    assert node[0].name == "Tania"
    assert node[0].age == 20

    node = await MultiRequiredPropNode.get_or_create({"name": "Tania", "age": 30})
    assert node[0].name == "Tania"
    assert node[0].age == 20  # Tania was fetched and not created, age is still 20

Custom Merge Keys
~~~~~~~~~~~~~~~~~
The ``get_or_create()`` method also supports the ``merge_by`` parameter for custom merge criteria::

    class User(StructuredNode):
        username = StringProperty(required=True, unique_index=True)
        email = StringProperty(required=True, unique_index=True)
        full_name = StringProperty()
        age = IntegerProperty()

    # Default behavior (merge by username + email)
    users = User.get_or_create({
        'username': 'johndoe',
        'email': 'john@example.com',
        'age': 30
    })

    # Custom merge by email only
    users = User.get_or_create({
        'username': 'johndoe',
        'email': 'john@example.com',
        'age': 31
    }, merge_by={'keys': ['email']})

    # Custom merge by username only
    users = User.get_or_create({
        'username': 'johndoe',
        'email': 'john.doe@newcompany.com',
        'age': 32
    }, merge_by={'label': 'User', 'keys': ['username']})

The same ``merge_by`` parameter format applies to both ``create_or_update()`` and ``get_or_create()`` methods.


Additionally, get_or_create() allows the "relationship" parameter to be passed. When a relationship is specified, the
matching is done based on that relationship and not globally. The relationship becomes one of the keys to match nodes::

    class Dog(StructuredNode):
        name = StringProperty(required=True)
        owner = RelationshipTo('Person', 'owner')

    class Person(StructuredNode):
        name = StringProperty(unique_index=True)
        pets = RelationshipFrom('Dog', 'owner')

    bob = Person.get_or_create({"name": "Bob"})[0]
    bobs_gizmo = Dog.get_or_create({"name": "Gizmo"}, relationship=bob.pets)

    tim = Person.get_or_create({"name": "Tim"})[0]
    tims_gizmo = Dog.get_or_create({"name": "Gizmo"}, relationship=tim.pets)

    # not the same gizmo
    assert bobs_gizmo[0] != tims_gizmo[0]

Relationship Properties
~~~~~~~~~~~~~~~~~~~~~~~
When using ``get_or_create()`` with a relationship, you can also set properties on the relationship using the ``rel_props`` parameter.
This is particularly useful when your relationship has a model with properties::

    from datetime import datetime, UTC

    class PetsRel(StructuredRel):
        since = DateTimeProperty()
        notes = StringProperty()

    class Dog(StructuredNode):
        name = StringProperty(required=True)
        owner = RelationshipTo('Person', 'OWNS', model=PetsRel)

    class Person(StructuredNode):
        name = StringProperty(unique_index=True)
        pets = RelationshipFrom('Dog', 'OWNS', model=PetsRel)

    bob = Person.get_or_create({"name": "Bob"})[0]
    since_date = datetime(2020, 1, 15, tzinfo=UTC)

    dogs = Dog.get_or_create(
        {"name": "Gizmo"},
        relationship=bob.pets,
        rel_props={"since": since_date, "notes": "Good boy!"},
    )

You can also create multiple nodes in a batch with the same relationship and relationship properties::

    alice = Person.get_or_create({"name": "Alice"})[0]
    since_date = datetime(2021, 5, 20, tzinfo=UTC)

    dogs = Dog.get_or_create(
        {"name": "Rex"},
        {"name": "Max"},
        {"name": "Luna"},
        relationship=alice.pets,
        rel_props={"since": since_date, "notes": "Adopted together"},
    )
