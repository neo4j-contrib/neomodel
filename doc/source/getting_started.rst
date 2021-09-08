===============
Getting started
===============

Connecting
==========

Before executing any neomodel code, set the connection url::

    from neomodel import config
    config.DATABASE_URL = 'bolt://neo4j:neo4j@localhost:7687'  # default

    # You can specify a database name: 'bolt://neo4j:neo4j@localhost:7687/mydb'

This must be called early on in your app, if you are using Django the `settings.py` file is ideal.

If you are using your neo4j server for the first time you will need to change the default password.
This can be achieved by visiting the neo4j admin panel (default: ``http://localhost:7474`` ).

You can also change the connection url at any time by calling ``set_connection``::

    from neomodel import db
    db.set_connection('bolt://neo4j:neo4j@localhost:7687')

The new connection url will be applied to the current thread or process.

In general however, it is better to `avoid setting database access credentials in plain sight <https://
www.ndss-symposium.org/wp-content/uploads/2019/02/ndss2019_04B-3_Meli_paper.pdf>`_. Neo4J defines a number of
`environment variables <https://neo4j.com/developer/kb/how-do-i-authenticate-with-cypher-shell-without-specifying-the-
username-and-password-on-the-command-line/>`_ that are used in its tools and these can be re-used for other applications
too.

These are:

* ``NEO4J_USERNAME``
* ``NEO4J_PASSWORD``
* ``NEO4J_BOLT_URL``

By setting these with (for example): ::

    $ export NEO4J_USERNAME=neo4j
    $ export NEO4J_PASSWORD=neo4j
    $ export NEO4J_BOLT_URL="bolt://$NEO4J_USERNAME:$NEO4J_PASSWORD@localhost:7687"

They can be accessed from a Python script via the ``environ`` dict of module ``os`` and be used to set the connection
with something like: ::

    import os
    from neomodel import config

    config.DATABASE_URL = os.environ["NEO4J_BOLT_URL"]

Defining Node Entities and Relationships
========================================

Below is a definition of two related nodes `Person` and `Country`: ::

    from neomodel import (config, StructuredNode, StringProperty, IntegerProperty,
        UniqueIdProperty, RelationshipTo)

    config.DATABASE_URL = 'bolt://neo4j:password@localhost:7687'

    class Country(StructuredNode):
        code = StringProperty(unique_index=True, required=True)

    class Person(StructuredNode):
        uid = UniqueIdProperty()
        name = StringProperty(unique_index=True)
        age = IntegerProperty(index=True, default=0)

        # traverse outgoing IS_FROM relations, inflate to Country objects
        country = RelationshipTo(Country, 'IS_FROM')

Nodes are defined in the same way classes are defined in Python with the only difference that data members of those
classes that are intended to be stored to the database must be defined as ``neomodel`` property objects. For more
detailed information on property objects please see the section on :ref:`property_types`.

**If** you have a need to attach "ad-hoc" properties to nodes that have not been specified at its definition, then 
consider deriving from the :ref:`semistructurednode_doc` class.

Relationships are defined via ``Relationship, RelationshipTo, RelationshipFrom`` objects. ``RelationshipTo,
RelationshipFrom`` can also specify the direction that a relationship would be allowed to be traversed. In this
particular example, ``Country`` objects would be accessible by ``Person`` objects but not the other way around.

When the relationship can be bi-directional, please avoid establishing two complementary ``RelationshipTo,
RelationshipFrom`` relationships and use ``Relationship``, on one of the class definitions instead. In all of these
cases, navigability matters more to the model as defined in Python. A relationship will be established in Neo4J but
in the case of ``Relationship`` it will be possible to be queried in either direction.

Neomodel automatically creates a label for each ``StructuredNode`` class in the database with the corresponding indexes
and constraints.

Applying constraints and indexes
================================
After creating a model in Python, any constraints or indexes need must be applied to Neo4j and ``neomodel`` provides a
script to automate this: ::

    $ neomodel_install_labels yourapp.py someapp.models --db bolt://neo4j:neo4j@localhost:7687

It is important to execute this after altering the schema and observe the number of classes it reports.

Remove existing constraints and indexes
=======================================
Similarly, ``neomodel`` provides a script to automate the removal of all existing constraints and indexes from
the database, when this is required: ::

    $ neomodel_remove_labels --db bolt://neo4j:neo4j@localhost:7687

After executing, it will print all indexes and constraints it has removed.

Create, Update, Delete operations
=================================

Using convenience methods such as::

    jim = Person(name='Jim', age=3).save() # Create
    jim.age = 4
    jim.save() # Update, (with validation)
    jim.delete()
    jim.refresh() # reload properties from the database
    jim.id # neo4j internal id

Retrieving nodes
================

Using the ``.nodes`` class property::

    # Return all nodes
    all_nodes = Person.nodes.all()

    # Returns Person by Person.name=='Jim' or raises neomodel.DoesNotExist if no match
    jim = Person.nodes.get(name='Jim')


``.nodes.all()`` and ``.nodes.get()`` can also accept a ``lazy=True`` parameter which will result in those functions
simply returning the node IDs rather than every attribute associated with that Node. ::

    # Will return None unless "bob" exists
    someone = Person.nodes.get_or_none(name='bob')

    # Will return the first Person node with the name bob. This raises neomodel.DoesNotExist if there's no match.
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

    for p in germany.inhabitant.all():
        print(p.name) # Jim

    len(germany.inhabitant) # 1

    # Find people called 'Jim' in germany
    germany.inhabitant.search(name='Jim')

    # Find all the people called in germany except 'Jim'
    germany.inhabitant.exclude(name='Jim')

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

