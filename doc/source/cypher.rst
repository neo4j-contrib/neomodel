==============
Cypher queries
==============

You may handle more complex queries via cypher. Each `StructuredNode` provides an 'inflate' class method,
this inflates nodes to their class. It is your responsibility to make sure nodes get inflated as the correct type::

    class Person(StructuredNode):
        def friends(self):
            results, columns = self.cypher("START a=node({self}) MATCH a-[:FRIEND]->(b) RETURN b")
            return [self.inflate(row[0]) for row in results]

The self query parameter is prepopulated with the current node id. It's possible to pass in your
own query parameters to the cypher method.

Stand alone
===========

Outside of a `StructuredNode`::

    # for standalone queries
    from neomodel import db
    results, meta = db.cypher_query(query, params)
    people = [Person.inflate(row[0]) for row in results]

Logging
=======

You may log queries and timings by setting the environment variable `NEOMODEL_CYPHER_DEBUG` to `1`.
