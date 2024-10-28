======================
Filtering and ordering
======================

For the examples in this section, we will be using the following model::

    class SupplierRel(StructuredRel):
        since = DateTimeProperty(default=datetime.now)


    class Supplier(StructuredNode):
        name = StringProperty()
        delivery_cost = IntegerProperty()


    class Coffee(StructuredNode):
        name = StringProperty(unique_index=True)
        price = IntegerProperty()
        suppliers = RelationshipFrom(Supplier, 'SUPPLIES', model=SupplierRel)

Filtering
=========

neomodel allows filtering on nodes' and relationships' properties. Filters can be combined using Django's Q syntax. It also allows multi-hop relationship traversals to filter on "remote" elements.

Filter methods
--------------

The ``.nodes`` property of a class returns all nodes of that type from the database.

This set (called `NodeSet`) can be iterated over and filtered on, using the `.filter` method::

    # nodes with label Coffee whose price is greater than 2
    high_end_coffees = Coffee.nodes.filter(price__gt=2)

    try:
        java = Coffee.nodes.get(name='Java')
    except DoesNotExist:
        # .filter will not throw an exception if no results are found
        # but .get will
        print("Couldn't find coffee 'Java'")

The filter method borrows the same Django filter format with double underscore prefixed operators:

- lt - less than
- gt - greater than
- lte - less than or equal to
- gte - greater than or equal to
- ne - not equal
- in - item in list
- isnull - `True` IS NULL, `False` IS NOT NULL
- exact - string equals
- iexact - string equals, case insensitive
- contains - contains string value
- icontains - contains string value, case insensitive
- startswith - starts with string value
- istartswith - starts with string value, case insensitive
- endswith - ends with string value
- iendswith - ends with string value, case insensitive
- regex - matches a regex expression
- iregex - matches a regex expression, case insensitive

These operators work with both `.get` and `.filter` methods.

Combining filters
-----------------

The filter method allows you to combine multiple filters::

    cheap_arabicas = Coffee.nodes.filter(price__lt=5, name__icontains='arabica')

These filters are combined using the logical AND operator. To execute more complex logic (for example, queries with OR statements), `Q objects <neomodel.Q>` can be used. This is borrowed from Django.

``Q`` objects can be combined using the ``&`` and ``|`` operators. Statements of arbitrary complexity can be composed by combining ``Q`` objects
with the ``&`` and ``|`` operators and use parenthetical grouping. Also, ``Q``
objects can be negated using the ``~`` operator, allowing for combined lookups
that combine both a normal query and a negated (``NOT``) query::

    Q(name__icontains='arabica') | ~Q(name__endswith='blend')

Chaining ``Q`` objects will join them as an AND clause::

    not_middle_priced_arabicas = Coffee.nodes.filter(
        Q(name__icontains='arabica'),
        Q(price__lt=5) | Q(price__gt=10)
    )

Traversals and filtering
------------------------

Sometimes you need to filter nodes based on other nodes they are connected to. This can be done by including a traversal in the `filter` method. ::

    # Find all suppliers of coffee 'Java' who have been supplying since 2007
    # But whose prices are greater than 5
    since_date = datetime(2007, 1, 1)
    java_old_timers = Coffee.nodes.filter(
            name='Java',
            suppliers__delivery_cost__gt=5,
            **{"suppliers|since__lt": since_date}
        )

In the example above, note the following syntax elements:

- The name of relationships as defined in the `StructuredNode` class is used to traverse relationships. `suppliers` in this example.
- Double underscore `__` is used to target a property of a node. `delivery_cost` in this example.
- A pipe `|` is used to separate the relationship traversal from the property filter. The filter also has to included in a `**kwargs` dictionary, because the pipe character would break the syntax. This is a special syntax to indicate that the filter is on the relationship itself, not on the node at the end of the relationship.
- The filter operators like lt, gt, etc. can be used on the filtered property.

Traversals can be of any length, with each relationships separated by a double underscore `__`, for example::

    # country is here a relationship between Supplier and Country
    Coffee.nodes.filter(suppliers__country__name='Brazil')

Enforcing relationship/path existence
-------------------------------------

The `has` method checks for existence of (one or more) relationships, in this case it returns a set of `Coffee` nodes which have a supplier::

    Coffee.nodes.has(suppliers=True)

This can be negated by setting `suppliers=False`, to find `Coffee` nodes without `suppliers`.

You can also filter on the existence of more complex traversals by using the `traverse_relations` method. See :ref:`Path traversal`.

Ordering
========

neomodel allows ordering by nodes' and relationships' properties. Order can be ascending or descending. Is also allows multi-hop relationship traversals to order on "remote" elements. Finally, you can inject raw Cypher clauses to have full control over ordering when necessary.

order_by
--------

Ordering results by a particular property is done via the `order_by` method::

    # Ascending sort
    for coffee in Coffee.nodes.order_by('price'):
        print(coffee, coffee.price)

    # Descending sort
    for supplier in Supplier.nodes.order_by('-delivery_cost'):
        print(supplier, supplier.delivery_cost)


Removing the ordering from a previously defined query, is done by passing `None` to `order_by`::

    # Sort in descending order
    suppliers = Supplier.nodes.order_by('-delivery_cost')

    # Don't order; yield nodes in the order neo4j returns them
    suppliers = suppliers.order_by(None)

For random ordering simply pass '?' to the order_by method::

    Coffee.nodes.order_by('?')

Traversals and ordering
-----------------------

Sometimes you need to order results based on properties situated on different nodes or relationships. This can be done by including a traversal in the `order_by` method. ::

    # Find the most expensive coffee to deliver
    # Then order by the date the supplier started supplying
    Coffee.nodes.order_by(
        '-suppliers__delivery_cost',
        'suppliers|since',
    )

In the example above, note the following syntax elements:

- The name of relationships as defined in the `StructuredNode` class is used to traverse relationships. `suppliers` in this example.
- Double underscore `__` is used to target a property of a node. `delivery_cost` in this example.
- A pipe `|` is used to separate the relationship traversal from the property filter. This is a special syntax to indicate that the filter is on the relationship itself, not on the node at the end of the relationship.

Traversals can be of any length, with each relationships separated by a double underscore `__`, for example::

    # country is here a relationship between Supplier and Country
    Coffee.nodes.order_by('suppliers__country__latitude')

RawCypher
---------

When you need more advanced ordering capabilities, for example to apply order to a transformed property, you can use the `RawCypher` method, like so::

    from neomodel.sync_.match import RawCypher

    class SoftwareDependency(AsyncStructuredNode):
        name = StringProperty()
        version = StringProperty()

    SoftwareDependency(name="Package2", version="1.4.0").save()
    SoftwareDependency(name="Package3", version="2.5.5").save()

    latest_dep = SoftwareDependency.nodes.order_by(
        RawCypher("toInteger(split($n.version, '.')[0]) DESC"),
    )

In the example above, note the `$n` placeholder in the `RawCypher` clause. This is a placeholder for the node being ordered (`SoftwareDependency` in this case).
