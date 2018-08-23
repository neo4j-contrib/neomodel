===============
Getting started
===============

Connecting
==========

Before executing any neomodel code set the connection url::

    from neomodel import config
    config.DATABASE_URL = 'bolt://neo4j:neo4j@localhost:7687'  # default

This needs to be called early on in your app, if you are using Django the `settings.py` file is ideal.

If you are using your neo4j server for the first time you will need to change the default password.
This can be achieved by visiting the neo4j admin panel (default: http://localhost:7474 ).

You can also change the connection url at any time by calling `set_connection`::

    from neomodel import db
    db.set_connection('bolt://neo4j:neo4j@localhost:7687')

The new connection url will be applied to the current thread or process.

Definition
==========

Below is a definition of two types of node `Person` and `Country`::

    from neomodel import (config, StructuredNode, StringProperty, IntegerProperty,
        UniqueIdProperty, RelationshipTo, RelationshipFrom)

    config.DATABASE_URL = 'bolt://neo4j:password@localhost:7687'

    class Country(StructuredNode):
        code = StringProperty(unique_index=True, required=True)

        # traverse incoming IS_FROM relation, inflate to Person objects
        inhabitant = RelationshipFrom('Person', 'IS_FROM')


    class Person(StructuredNode):
        uid = UniqueIdProperty()
        name = StringProperty(unique_index=True)
        age = IntegerProperty(index=True, default=0)

        # traverse outgoing IS_FROM relations, inflate to Country objects
        country = RelationshipTo(Country, 'IS_FROM')


There is one type of relationship present `IS_FROM`, we are defining two different ways for traversing it
one accessible via `Person` objects and one via `Country` objects

We can use the `Relationship` class as opposed to the `RelationshipTo` or `RelationshipFrom`
if we don't want to specify a direction.

Neomodel automatically creates a label for each `StructuredNode` class in the database
with the corresponding indexes and constraints.

Setup constraints and indexes
=============================
After creating node definitions in python, any constraints or indexes need to be added to Neo4j.

Neomodel provides a script to automate this::

    $ neomodel_install_labels yourapp.py someapp.models --db bolt://neo4j:neo4j@localhost:7687

It is important to execute this after altering the schema. Keep an eye on the number of classes it detects each time.

Remove existing constraints and indexes
=======================================
For deleting all existing constraints and indexes from database, neomodel provides a script to automate this::

    $ neomodel_remove_labels --db bolt://neo4j:neo4j@localhost:7687

After executing, it will print all indexes and constraints it has deleted.

Create, Update, Delete
======================

Using convenience methods such as::

    jim = Person(name='Jim', age=3).save()
    jim.age = 4
    jim.save() # validation happens here
    jim.delete()
    jim.refresh() # reload properties from neo
    jim.id # neo4j internal id

Retrieving nodes
================

Using the '.nodes' class property::

    # raises Person.DoesNotExist if no match
    jim = Person.nodes.get(name='Jim')

    # Will return None unless bob exists
    someone = Person.nodes.get_or_none(name='bob')

    # Will return the first Person node with the name bob. This raises Person.DoesNotExist if there's no match.
    someone = Person.nodes.first(name='bob')

    # Will return the first Person node with the name bob or None if there's no match
    someone = Person.nodes.first_or_none(name='bob')

    # Return set of nodes
    people = Person.nodes.filter(age__gt=3)

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

    # Remove Jim's country relationship with Germany
    jim.country.disconnect(germany)

    usa = Country(code='US').save()
    jim.country.connect(usa)
    jim.country.connect(germany)

    # Remove all of Jim's country relationships
    jim.country.disconnect_all()

    jim.country.connect(usa)
    # Replace Jim's country relationship with a new one
    jim.country.replace(germany)
