======================
Batch nodes operations
======================

All batch operations can be executed with one or more node. These are carried out in a transaction if one was defined.
These methods except an optional "streaming" parameter, when set to ``True``, ``StructuredNode`` s are returned by an
iterable generator instead of a simple list.

create()
--------
Atomically create multiple nodes in a single operation, using a single HTTP request::

    people = Person.create(
        {'name': 'Tim', 'age': 83},
        {'name': 'Bob', 'age': 23},
        {'name': 'Jill', 'age': 34},
    )

This is useful for creating large sets of data. It's worth experimenting with the size of batches
to find the optimum performance. A suggestion is to use batch sizes of around 300 to 500 nodes.

create_or_update()
------------------
Atomically create or update nodes in a single operation, using a single HTTP request::

    people = Person.create_or_update(
        {'name': 'Tim', 'age': 83},
        {'name': 'Bob', 'age': 23},
        {'name': 'Jill', 'age': 34},
    )

    more_people = Person.create_or_update(
        {'name': 'Tim', 'age': 73},
        {'name': 'Bob', 'age': 35},
        {'name': 'Jane', 'age': 24},
    )

This is useful for ensuring data is up to date, each node is matched by its' required and/or unique properties. Any
additional properties will be set on a newly created or an existing node. Each operation is atomic.

get_or_create()
---------------
Atomically get or create nodes in a single operation, using a single HTTP request::

    people = Person.get_or_create(
        {'name': 'Tim'},
        {'name': 'Bob'},
    )
    people_with_jill = Person.get_or_create(
        {'name': 'Tim'},
        {'name': 'Bob'},
        {'name': 'Jill'},
    )
    # are same nodes
    assert people[0] == people_with_jill[0]
    assert people[1] == people_with_jill[1]

This is useful for ensuring specific nodes exist, only and all required properties must be specified to ensure
uniqueness. In this example 'Tim' and 'Bob' are created on the first call, and are retrieved in the second call.

Additionally, get_or_create() allows the "relationship" parameter to be passed. When a relationship is specified, the
matching is done based on that relationship and not globally::

    class Dog(StructuredNode):
        name = StringProperty(required=True)

        owner = RelationshipTo('Person, 'owner')

    class Person(StructuredNode):
        name = StringProperty(unique_index=True)

        pets = RelationshipFrom('Dog, 'owner')

    bob = Person.get_or_create({"name": "Tom"})
    bobs_gizmo = Dog.get_or_create({"name": "Gizmo"}, relationship=bob.pets)

    tim = Person.get_or_create({"name": "Tim"})
    tims_gizmo = Dog.get_or_create({"name": "Gizmo"}, relationship=tim.pets)

    # not the same gizmo
    assert bobs_gizmo[0] != tims_gismo[0]

In case when the only required property is unique, the operation is redundant. However with simple required properties,
the relationship becomes a part of the unique identifier.

Using streaming=True
--------------------
This parameter is supported by all batch operations::

    for person in Person.create({"name": "Bob"}, {"name": "Tim"}, streaming=True):
        if person.name == "Bob":
            continue

        yield person

IMPORTANT: In streaming mode results are not fetched inside an existing transaction.
