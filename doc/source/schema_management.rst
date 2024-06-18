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
- ``fulltext_index=True``: This will create a FULLTEXT index on the property. Only available for Neo4j version 5.16 or higher. With this one, you can define the following options:
    - ``fulltext_analyzer``: The analyzer to use. The default is ``standard-no-stop-words``.
    - ``fulltext_eventually_consistent``: Whether the index should be eventually consistent. The default is ``False``.
  
Please refer to the `Neo4j documentation <https://neo4j.com/docs/cypher-manual/current/indexes/semantic-indexes/full-text-indexes/#configuration-settings>`_. for more information on fulltext indexes.

- Vector indexes (Work in progress)

Those indexes are available for both node- and relationship properties.

.. note:: 
    Yes, you can create multiple indexes of a different type on the same property. For example, a default index and a fulltext index.

.. note:: 
    For the semantic indexes (fulltext and vector), this allows you to create indexes, but searching those indexes require using Cypher queries.
    This is because Cypher only supports querying those indexes through a specific procedure for now.

Full example: ::

    class VeryIndexedNode(StructuredNode):
        name = StringProperty(
            index=True, 
            fulltext_index=True, 
            fulltext_analyzer='english', 
            fulltext_eventually_consistent=True
        )

Constraints
===========

The following constraints are supported:

- ``unique_index=True``: This will create a uniqueness constraint on the property. Available for both nodes and relationships (Neo4j version 5.7 or higher).

.. note::
    The uniquess constraint of Neo4j is not supported as such, but using ``required=True`` on a property serves the same purpose.


Extracting the schema from a database
=====================================

You can extract the schema from an existing database using the ``neomodel_inspect_database`` script (:ref:`inspect_database_doc`).
This script will output the schema in the neomodel format, including indexes and constraints.