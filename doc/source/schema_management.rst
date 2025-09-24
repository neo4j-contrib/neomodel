=================
Schema management
=================

Neo4j allows a flexible schema management, where you can define indexes and constraints on the properties of nodes and relationships.
To learn more, please refer to the `Neo4j schema documentation <https://neo4j.com/docs/getting-started/cypher-intro/schema/>`_.

Defining your model
-------------------

neomodel allows you to define indexes and constraints in your node and relationship classes, like so: ::

    from neomodel import (StructuredNode, StructuredRel, StringProperty,
        IntegerProperty, RelationshipTo)
        
    class LocatedIn(StructuredRel):
        since = IntegerProperty(index=True)

    class Country(StructuredNode):
        code = StringProperty(unique_index=True)

    class City(StructuredNode):
        name = StringProperty(index=True)
        country = RelationshipTo(Country, 'FROM_COUNTRY', model=LocatedIn)


Applying constraints and indexes
--------------------------------
After creating your model, any constraints or indexes must be applied to Neo4j and ``neomodel`` provides a
script (:ref:`neomodel_install_labels`) to automate this: ::

    $ neomodel_install_labels yourapp.py someapp.models --db bolt://neo4j_username:neo4j_password@localhost:7687

It is important to execute this after altering the schema and observe the number of classes it reports.

Ommitting the ``--db`` argument will default to the ``NEO4J_BOLT_URL`` environment variable. This is useful for masking
your credentials.

.. note::
    The script will only create indexes and constraints that are defined in your model classes. It will not remove any
    existing indexes or constraints that are not defined in your model classes.

Indexes
=======

The following indexes are supported:

- ``index=True``: This will create the default Neo4j index on the property (currently RANGE).
- :ref:`Semantic Indexes`

.. note:: 
    Yes, you can create multiple indexes of a different type on the same property. For example, a default index and a fulltext index.

Constraints
===========

The following constraints are supported:

- ``unique_index=True``: This will create a uniqueness constraint on the property. Available for both nodes and relationships (Neo4j version 5.7 or higher).

.. note::
    The uniqueness constraint of Neo4j is not supported as such, but using ``required=True`` on a property serves the same purpose.


Extracting the schema from a database
=====================================

You can extract the schema from an existing database using the ``neomodel_inspect_database`` script (:ref:`inspect_database_doc`).
This script will output the schema in the neomodel format, including indexes and constraints.
