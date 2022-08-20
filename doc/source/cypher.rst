==============
Cypher queries
==============

You may handle more complex queries via cypher. Each `StructuredNode` provides an 'inflate' class method,
this inflates nodes to their class. It is your responsibility to make sure nodes get inflated as the correct type::

    class Person(StructuredNode):
        def friends(self):
            results, columns = self.cypher("MATCH (a:Person) WHERE id(a)=$self MATCH (a)-[:FRIEND]->(b) RETURN b")
            return [self.inflate(row[0]) for row in results]

The self query parameter is prepopulated with the current node id named `self`. It's possible to pass in your
own query parameters to the cypher method. You can use them as you would cypher parameters (``$name`` to access the parameter named `name`)

Stand alone
===========

Outside of a `StructuredNode`::

    # for standalone queries
    from neomodel import db
    results, meta = db.cypher_query(query, params, resolve_objects=True)

The ``resolve_objects`` parameter automatically inflates the returned nodes to their defined classes (this is turned **off** by default). See :ref:`automatic_class_resolution` for details and possible pitfalls.

Logging
=======

You may log queries and timings by setting the environment variable `NEOMODEL_CYPHER_DEBUG` to `1`.

Utilities
=========
The following utility functions are available::

    clear_neo4j_database(db)  # deletes all nodes and relationships

    # Change database password (you will need to call db.set_connection(...) after
    change_neo4j_password(db, new_password)
