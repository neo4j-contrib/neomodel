===============
Getting started
===============

Connecting
==========

Before executing any neomodel code set the connection url as below::

    from neomodel import db
    db.set_connection('bolt://neo4j:neo4j@localhost:7687')

Note that if you are using Django this code should live in your settings.py file.

*If you are using your neo4j server for the first time you will need to change the default password*.
This can be achieved by visiting the neo4j admin panel (default: http://localhost:7474 ).

Calling `set_connection()` can be called at any point in execution but be warned that it applies to the whole thread.

Definition
==========

In the example below, there is one type of relationship present `IS_FROM`,
we are defining two different ways for traversing it
one accessible via Person objects and one via Country objects::

    from neomodel import (StructuredNode, StringProperty, IntegerProperty,
        RelationshipTo, RelationshipFrom)

    class Country(StructuredNode):
        code = StringProperty(unique_index=True, required=True)

        # traverse incoming IS_FROM relation, inflate to Person objects
        inhabitant = RelationshipFrom('Person', 'IS_FROM')


    class Person(StructuredNode):
        name = StringProperty(unique_index=True)
        age = IntegerProperty(index=True, default=0)

        # traverse outgoing IS_FROM relations, inflate to Country objects
        country = RelationshipTo(Country, 'IS_FROM')

We can use the `Relationship` class if we don't want to specify a direction.

Create, Save, Delete
====================

Using convenient methods::

    jim = Person(name='Jim', age=3).save()
    jim.age = 4
    jim.save() # validation happens here
    jim.delete()
    jim.refresh() # reload properties from neo
    jim.id # neo4j internal id

Relationships
=============

Working with relationships::

    germany = Country(code='DE').save()
    jim.country.connect(germany)

    if jim.country.is_connected(germany):
        print("Jim's from Germany")

    for p in germany.inhabitant.all()
        print(p.name) # Jim

    len(germany.inhabitant) # 1

    # Find people called 'Jim' in germany
    germany.inhabitant.search(name='Jim')

    jim.country.disconnect(germany)
