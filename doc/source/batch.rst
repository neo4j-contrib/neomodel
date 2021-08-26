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
Atomically create or update nodes in a single operation::

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

This is useful for ensuring data is up to date, each node is matched by its required and/or unique properties. Any
additional properties will be set on a newly created or an existing node.

It is important to provide unique identifiers where known, any fields with default values that are omitted will be generated.

get_or_create()
---------------
Atomically get or create nodes in a single operation::

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

This is useful for ensuring specific nodes exist only and all required properties must be specified to ensure
uniqueness. In this example 'Tim' and 'Bob' are created on the first call, and are retrieved in the second call.

Additionally, get_or_create() allows the "relationship" parameter to be passed. When a relationship is specified, the
matching is done based on that relationship and not globally::

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

In case when the only required property is unique, the operation is redundant. However with simple required properties,
the relationship becomes a part of the unique identifier.
