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

Integrations
============

Pandas
------

First, you need to install pandas by yourself. We do not include it by default to keep the package size controlled::

    # When installing neomodel
    pip install neomodel[pandas]

    # Or separately
    pip install pandas

You can use the `pandas` integration to return a `DataFrame` or `Series` object::

    from neomodel import db
    from neomodel.integration.pandas import to_dataframe, to_series

    df = to_dataframe(db.cypher_query("MATCH (a:Person) RETURN a.name AS name, a.born AS born"))
    series = to_series(db.cypher_query("MATCH (a:Person) RETURN a.name AS name"))

Numpy
------

First, you need to install numpy by yourself. We do not include it by default to keep the package size controlled::

    # When installing neomodel
    pip install neomodel[numpy]

    # Or separately
    pip install numpy

You can use the `numpy` integration to return a `ndarray` object::

    from neomodel import db
    from neomodel.integration.numpy import to_ndarray

    array = to_ndarray(db.cypher_query("MATCH (a:Person) RETURN a.name AS name, a.born AS born"))

Logging
=======

You may log queries and timings by setting the environment variable `NEOMODEL_CYPHER_DEBUG` to `1`.

Utilities
=========
The following utility functions are available::

    # Deletes all nodes and relationships.
    # Optionally, can drop all constraints and/or indexes. It preserves the default lookup indexes
    clear_neo4j_database(db, clear_constraints=False, clear_indexes=False)

    # Change database password (you will need to call db.set_connection(...) to reset connection)
    change_neo4j_password(db, user, new_password)
