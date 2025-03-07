.. _Path traversal:

==============
Path traversal
==============

Neo4j is about traversing the graph, which means leveraging nodes and relations between them. This section will show you how to traverse the graph using neomodel.

We will cover two methods : `traverse_relations` and `fetch_relations`. Those two methods are *mutually exclusive*, so you cannot chain them.

For the examples in this section, we will be using the following model::

    class Country(StructuredNode):
        country_code = StringProperty(unique_index=True)
        name = StringProperty()

    class Supplier(StructuredNode):
        name = StringProperty()
        delivery_cost = IntegerProperty()
        country = RelationshipTo(Country, 'ESTABLISHED_IN')

    class Coffee(StructuredNode):
        name = StringProperty(unique_index=True)
        price = IntegerProperty()
        suppliers = RelationshipFrom(Supplier, 'SUPPLIES')

Traverse relations
------------------

The `traverse_relations` method allows you to filter on the existence of more complex traversals. For example, to find all `Coffee` nodes that have a supplier, and retrieve the country of that supplier, you can do::

    Coffee.nodes.traverse_relations(country='suppliers__country').all()

This will generate a Cypher MATCH clause that enforces the existence of at least one path like `Coffee<--Supplier-->Country`.

The `Country` nodes matched will be made available for the rest of the query, with the variable name `country`. Note that this aliasing is optional. See :ref:`Advanced query operations` for examples of how to use this aliasing.

.. note::

    The `traverse_relations` method can be used to traverse multiple relationships, like::

        Coffee.nodes.traverse_relations('suppliers__country', 'pub__city').all()

    This will generate a Cypher MATCH clause that enforces the existence of at least one path like `Coffee<--Supplier-->Country` and `Coffee<--Pub-->City`.

Fetch relations
---------------

The syntax for `fetch_relations` is similar to `traverse_relations`, except that the generated Cypher will return all traversed objects (nodes and relations)::

    Coffee.nodes.fetch_relations(country='suppliers__country').all()

.. note::

    Any relationship that you intend to traverse using this method **MUST have a model defined**, even if only the default StructuredRel, like::
        
        class Person(StructuredNode):
            country = RelationshipTo(Country, 'IS_FROM', model=StructuredRel)

    Otherwise, neomodel will not be able to determine which relationship model to resolve into, and will fail.

Optional match
--------------

With both `traverse_relations` and `fetch_relations`, you can force the use of an ``OPTIONAL MATCH`` statement using the following syntax::

    from neomodel.match import Optional

    # Return the Person nodes, and if they have suppliers, return the suppliers as well
    results = Coffee.nodes.fetch_relations(Optional('suppliers')).all()

.. note::

   You can fetch one or more relations within the same call
   to `.fetch_relations()` and you can mix optional and non-optional
   relations, like::

    Person.nodes.fetch_relations('city__country', Optional('country')).all()

Unique variables
----------------

If you want to use the same variable name for traversed nodes when chaining traversals, you can use the `unique_variables` method::

    # This does not guarantee that coffees__species will traverse the same nodes as coffees
    # So coffees__species can traverse the Coffee node "Gold 3000"
    nodeset = (
        Supplier.nodes.fetch_relations("coffees", "coffees__species")
        .filter(coffees__name="Nescafe")
    )

    # This guarantees that coffees__species will traverse the same nodes as coffees
    # So when fetching species, it will only fetch those of the Coffee node "Nescafe"
    nodeset = (
        Supplier.nodes.fetch_relations("coffees", "coffees__species")
        .filter(coffees__name="Nescafe")
        .unique_variables("coffees")
    )

Resolve results
---------------

By default, `fetch_relations` will return a list of tuples. If your path looks like ``(startNode:Coffee)<-[r1]-(middleNode:Supplier)-[r2]->(endNode:Country)``,
then you will get a list of results, where each result is a list of ``(startNode, r1, middleNode, r2, endNode)``.
These will be resolved by neomodel, so ``startNode`` will be a ``Coffee`` class as defined in neomodel for example.

Using the `resolve_subgraph` method, you can get instead a list of "subgraphs", where each returned `StructuredNode` element will contain its relations and neighbour nodes. For example::

    results = Coffee.nodes.fetch_relations('suppliers__country').resolve_subgraph().all()

In this example, `results[0]` will be a `Coffee` object, with a `_relations` attribute. This will in turn have a `suppliers` and a `suppliers_relationship` attribute, which will contain the `Supplier` object and the relation object respectively. Recursively, the `Supplier` object will have a `country` attribute, which will contain the `Country` object.

.. note:: 

    The `resolve_subgraph` method is only available for `fetch_relations` queries. This is because `traverse_relations` queries do not return any relations, and thus there is no need to resolve them.

