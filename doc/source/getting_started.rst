===============
Getting started
===============

Connecting
==========

Before executing any neomodel code, set the connection url::

    from neomodel import config
    config.DATABASE_URL = 'bolt://neo4j:neo4j@localhost:7687'  # default

This must be called early on in your app, if you are using Django the `settings.py` file is ideal.

See the Configuration page (:ref:`connection_options_doc`) for config options.

If you are using your neo4j server for the first time you will need to change the default password.
This can be achieved by visiting the neo4j admin panel (default: ``http://localhost:7474`` ).

Querying the graph
==================

neomodel is mainly used as an OGM (see next section), but you can also use it for direct Cypher queries : ::

    results, meta = db.cypher_query("RETURN 'Hello World' as message")


Defining Node Entities and Relationships
========================================

Below is a definition of three related nodes `Person`, `City` and `Country`: ::

    from neomodel import (config, StructuredNode, StringProperty, IntegerProperty,
        UniqueIdProperty, RelationshipTo)

    config.DATABASE_URL = 'bolt://neo4j:password@localhost:7687'

    class Country(StructuredNode):
        code = StringProperty(unique_index=True, required=True)

    class City(StructuredNode):
        name = StringProperty(required=True)
        country = RelationshipTo(Country, 'FROM_COUNTRY')

    class Person(StructuredNode):
        uid = UniqueIdProperty()
        name = StringProperty(unique_index=True)
        age = IntegerProperty(index=True, default=0)

        # traverse outgoing IS_FROM relations, inflate to Country objects
        country = RelationshipTo(Country, 'IS_FROM')

        # traverse outgoing LIVES_IN relations, inflate to City objects
        city = RelationshipTo(City, 'LIVES_IN')

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

Database Inspection - Requires APOC
===================================
You can inspect an existing Neo4j database to generate a neomodel definition file using the ``inspect`` command::

    $ neomodel_inspect_database -db bolt://neo4j:neo4j@localhost:7687 --write-to yourapp/models.py

This will generate a file called ``models.py`` in the ``yourapp`` directory. This file can be used as a starting point,
and will contain the necessary module imports, as well as class definition for nodes and, if relevant, relationships.

Note that you can also print the output to the console instead of writing a file by omitting the ``--write-to`` option.

.. note::

    This command will only generate the definition for nodes and relationships that are present in the
    database. If you want to generate a complete definition file, you will need to add the missing classes manually.

    Also, this has only been tested with single-label nodes. If you have multi-label nodes, you will need to double check,
    and add the missing labels manually in the relevant way.

    Finally, relationship cardinality is guessed from the database by looking at existing relationships, so it might
    guess wrong on edge cases.

.. warning:: 

    The script relies on the method apoc.meta.cypher.types to parse property types. So APOC must be installed on your Neo4j server
    for this script to work.

Applying constraints and indexes
================================
After creating a model in Python, any constraints or indexes must be applied to Neo4j and ``neomodel`` provides a
script (:ref:`neomodel_install_labels`) to automate this: ::

    $ neomodel_install_labels yourapp.py someapp.models --db bolt://neo4j:neo4j@localhost:7687

It is important to execute this after altering the schema and observe the number of classes it reports.

Remove existing constraints and indexes
=======================================
Similarly, ``neomodel`` provides a script (:ref:`neomodel_remove_labels`) to automate the removal of all existing constraints and indexes from
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
    jim.element_id # neo4j internal element id

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
    berlin = City(name='Berlin').save()
    berlin.country.connect(germany)
    jim.city.connect(berlin)

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


Retrieving additional relations
===============================

To avoid queries multiplication, you have the possibility to retrieve
additional relations with a single call::

    # The following call will generate one MATCH with traversal per
    # item in .fetch_relations() call
    results = Person.nodes.all().fetch_relations('country')
    for result in results:
        print(result[0]) # Person
        print(result[1]) # associated Country

You can traverse more than one hop in your relations using the
following syntax::

    # Go from person to City then Country
    Person.nodes.all().fetch_relations('city__country')

You can also force the use of an ``OPTIONAL MATCH`` statement using
the following syntax::

    from neomodel.match import Optional

    results = Person.nodes.all().fetch_relations(Optional('country'))

.. note::

   You can fetch one or more relations within the same call
   to `.fetch_relations()` and you can mix optional and non-optional
   relations, like::

    Person.nodes.all().fetch_relations('city__country', Optional('country'))

.. warning::

   This feature is still a work in progress for extending path traversal and fecthing.
   It currently stops at returning the resolved objects as they are returned in Cypher.
   So for instance, if your path looks like ``(startNode:Person)-[r1]->(middleNode:City)<-[r2]-(endNode:Country)``,
   then you will get a list of results, where each result is a list of ``(startNode, r1, middleNode, r2, endNode)``.
   These will be resolved by neomodel, so ``startNode`` will be a ``Person`` class as defined in neomodel for example.

   If you want to go further in the resolution process, you have to develop your own parser (for now).

