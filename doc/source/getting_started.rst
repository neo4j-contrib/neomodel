===============
Getting started
===============

Connecting
==========

Before executing any neomodel code set the connection url::

    from neomodel import config
    config.DATABASE_URL = 'bolt://neo4j:neo4j@localhost:7687'  # default

This needs to be called early on in your app, if you are using Django the settings.py file is ideal.

If you are using your neo4j server for the first time you will need to change the default password.
This can be achieved by visiting the neo4j admin panel (default: http://localhost:7474 ).

You can also change the connection url at any time by calling `set_connection`::

    from neomodel import db
    db.set_connection('bolt://neo4j:neo4j@localhost:7687')

The new connection url will be applied to the current thread or process.

Definition
==========

Below is a definition of two types of node `Person` and `Country::

    from neomodel import (config, StructuredNode, StringProperty, IntegerProperty,
        RelationshipTo, RelationshipFrom)

    config.DATABASE_URL = 'bolt://neo4j:password@localhost:7687'

    class Country(StructuredNode):
        code = StringProperty(unique_index=True, required=True)

        # traverse incoming IS_FROM relation, inflate to Person objects
        inhabitant = RelationshipFrom('Person', 'IS_FROM')


    class Person(StructuredNode):
        name = StringProperty(unique_index=True)
        age = IntegerProperty(index=True, default=0)

        # traverse outgoing IS_FROM relations, inflate to Country objects
        country = RelationshipTo(Country, 'IS_FROM')


There is one type of relationship present `IS_FROM`, we are defining two different ways for traversing it
one accessible via Person objects and one via Country objects

We can use the `Relationship` class as opposed to the `RelationshipTo` or `RelationshipFrom`
if we don't want to specify a direction.

Neomodel automatically creates a label for each StructuredNode class in the database
 with the corresponding indexes and constraints.

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
