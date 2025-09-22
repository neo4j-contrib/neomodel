.. _Advanced query operations:

=========================
Advanced query operations
=========================

neomodel provides ways to enhance your queries beyond filtering and traversals.

Annotate - Aliasing
-------------------

The `annotate` method allows you to add transformations to your elements. To learn more about the available transformations, keep reading this section.

Aggregations
------------

neomodel implements some of the aggregation methods available in Cypher:

- Collect (with distinct option)
- Last

These are usable in this way::

    from neomodel.sync_.match import Collect, Last

    # distinct is optional, and defaults to False. When true, objects are deduplicated
    Supplier.nodes.traverse_relations(available_species="coffees__species")
        .annotate(Collect("available_species", distinct=True))
        .all()

    # Last is used to get the last element of a list
    Supplier.nodes.traverse_relations(available_species="coffees__species")
        .annotate(Last(Collect("last_species")))
        .all()

Note how `annotate` is used to add the aggregation method to the query.

.. note::
    Using the Last() method right after a Collect() without having set an ordering will return the last element in the list as it was returned by the database.

    This is probably not what you want ; which means you must provide an explicit ordering. To do so, you cannot use neomodel's `order_by` method, but need an intermediate transformation step (see below).

    This is because the order_by method adds ordering as the very last step of the Cypher query ; whereas in the present example, you want to first order Species, then get the last one, and then finally return your results. In other words, you need an intermediate WITH Cypher clause.

Intermediate transformations
----------------------------

The `intermediate_transform` method basically allows you to add a WITH clause to your query. This is useful when you need to perform some operations on your results before returning them.

As discussed in the note above, this is for example useful when you need to order your results before applying an aggregation method, like so::

    from neomodel.sync_.match import Collect, Last

    # This will return all Coffee nodes, with their most expensive supplier
    Coffee.nodes.traverse_relations(suppliers="suppliers")
        .intermediate_transform(
            {"suppliers": {"source": "suppliers"}}, ordering=["suppliers.delivery_cost"]
        )
        .annotate(supps=Last(Collect("suppliers")))

Options for `intermediate_transform` *variables* are:

- `source`: `string` or `Resolver` - the variable to use as source for the transformation. Works with resolvers (see below).
- `source_prop`: `string` - optionally, a property of the source variable to use as source for the transformation.
- `include_in_return`: `bool` - whether to include the variable in the return statement. Defaults to False.

Additional options for the `intermediate_transform` method are:

- `distinct`: `bool` - whether to deduplicate the results. Defaults to False.

Here is a full example::

    await Coffee.nodes.fetch_relations("suppliers")
        .intermediate_transform(
            {
                "coffee": {"source": "coffee"},
                "suppliers": {"source": NodeNameResolver("suppliers")},
                "r": {"source": RelationNameResolver("suppliers")},
                "coffee": {"source": "coffee", "include_in_return": True}, # Only coffee will be returned
                "suppliers": {"source": NodeNameResolver("suppliers")},
                "r": {"source": RelationNameResolver("suppliers")},
                "cost": {
                    "source": NodeNameResolver("suppliers"),
                    "source_prop": "delivery_cost",
                },
            },
            distinct=True,
            ordering=["-r.since"],
        )
        .annotate(oldest_supplier=Last(Collect("suppliers")))
        .all()

Subqueries
----------

The `subquery` method allows you to perform a `Cypher subquery <https://neo4j.com/docs/cypher-manual/current/subqueries/call-subquery/>`_ inside your query. This allows you to perform operations in isolation to the rest of your query::

    from neomodel.sync_match import Collect, Last

    # This will create a CALL{} subquery
    # And return a variable named supps usable in the rest of your query
    Coffee.nodes.filter(name="Espresso")
    .subquery(
        Coffee.nodes.traverse_relations(suppliers="suppliers")
        .intermediate_transform(
            {"suppliers": {"source": "suppliers"}}, ordering=["suppliers.delivery_cost"]
        )
        .annotate(supps=Last(Collect("suppliers"))),
        ["supps"],
        [NodeNameResolver("self")]
    )

Options for `subquery` calls are:

- `return_set`: list of `string` - the subquery variables that should be included in the outer query result
- `initial_context`: optional list of `string` or `Resolver` - the outer query variables that will be injected at the begining of the subquery

.. note::
   In the example above, we reference `self` to be included in the initial context. It will actually inject the outer variable corresponding to `Coffee` node.

   We know this is confusing to read, but have not found a better way to do this yet. If you have any suggestions, please let us know.

Helpers
-------

Reading the sections above, you may have noticed that we used explicit aliasing in the examples, as in::

    traverse_relations(suppliers="suppliers")

This allows you to reference the generated Cypher variables in your transformation steps, for example::

    traverse_relations(suppliers="suppliers").annotate(Collect("suppliers"))

In some cases though, it is not possible to set explicit aliases, for example when using `fetch_relations`. In these cases, neomodel provides `resolver` methods, so you do not have to guess the name of the variable in the generated Cypher. Those are `NodeNameResolver` and `RelationshipNameResolver`. For example::

    from neomodel.sync_match import Collect, NodeNameResolver, RelationshipNameResolver

    Supplier.nodes.fetch_relations("coffees__species")
        .annotate(
            all_species=Collect(NodeNameResolver("coffees__species"), distinct=True),
            all_species_rels=Collect(
                RelationNameResolver("coffees__species"), distinct=True
            ),
        )
        .all()

.. note:: 

    When using the resolvers in combination with a traversal as in the example above, it will resolve the variable name of the last element in the traversal - the Species node for NodeNameResolver, and Coffee--Species relationship for RelationshipNameResolver.

Another example is to reference the root node itself::

    subquery = await Coffee.nodes.subquery(
        Coffee.nodes.traverse_relations(suppliers="suppliers")
        .intermediate_transform(
            {"suppliers": {"source": "suppliers"}}, ordering=["suppliers.delivery_cost"]
        )
        .annotate(supps=Last(Collect("suppliers"))),
        ["supps"],
        [NodeNameResolver("self")], # This is the root Coffee node
    )
