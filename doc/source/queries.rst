================
Advanced queries
================

Neomodel contains an API for querying sets of nodes without having to write cypher::

    class SupplierRel(StructuredRel):
        since = DateTimeProperty(default=datetime.now)


    class Supplier(StructuredNode):
        name = StringProperty()
        delivery_cost = IntegerProperty()
        coffees = RelationshipTo('Coffee', 'SUPPLIES')


    class Coffee(StructuredNode):
        name = StringProperty(unique_index=True)
        price = IntegerProperty()
        suppliers = RelationshipFrom(Supplier, 'SUPPLIES', model=SupplierRel)

Node sets and filtering
=======================

The ``.nodes`` property of a class returns all nodes of that type from the database.

This set (or `NodeSet`) can be iterated over and filtered on. Under the hood it uses labels introduced in Neo4J 2::

    # nodes with label Coffee whose price is greater than 2
    Coffee.nodes.filter(price__gt=2)

    try:
        java = Coffee.nodes.get(name='Java')
    except Coffee.DoesNotExist:
        print "Couldn't find coffee 'Java'"

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

Complex lookups with ``Q`` objects
==================================

Keyword argument queries -- in `filter`,
etc. -- are "AND"ed together. To execute more complex queries (for
example, queries with ``OR`` statements), `Q objects <neomodel.Q>` can 
be used.

A `Q object` (``neomodel.Q``) is an object
used to encapsulate a collection of keyword arguments. These keyword arguments
are specified as in "Field lookups" above.

For example, this ``Q`` object encapsulates a single ``LIKE`` query::

    from neomodel import Q
    Q(name__startswith='Py')

``Q`` objects can be combined using the ``&`` and ``|`` operators. When an
operator is used on two ``Q`` objects, it yields a new ``Q`` object.

For example, this statement yields a single ``Q`` object that represents the
"OR" of two ``"name__startswith"`` queries::

    Q(name__startswith='Py') | Q(name__startswith='Jav')

This is equivalent to the following SQL ``WHERE`` clause::

    WHERE name STARTS WITH 'Py' OR name STARTS WITH 'Jav'

Statements of arbitrary complexity can be composed by combining ``Q`` objects
with the ``&`` and ``|`` operators and use parenthetical grouping. Also, ``Q``
objects can be negated using the ``~`` operator, allowing for combined lookups
that combine both a normal query and a negated (``NOT``) query::

    Q(name__startswith='Py') | ~Q(year=2005)

Each lookup function that takes keyword-arguments
(e.g. `filter`, `exclude`, `get`) can also be passed one or more
``Q`` objects as positional (not-named) arguments. If multiple
``Q`` object arguments are provided to a lookup function, the arguments will be "AND"ed
together. For example::

    Lang.nodes.filter(
        Q(name__startswith='Py'),
        Q(year=2005) | Q(year=2006)
    )

This roughly translates to the following Cypher query::

    MATCH (lang:Lang) WHERE name STARTS WITH 'Py'
        AND (year = 2005 OR year = 2006)
        return lang;

Lookup functions can mix the use of ``Q`` objects and keyword arguments. All
arguments provided to a lookup function (be they keyword arguments or ``Q``
objects) are "AND"ed together. However, if a ``Q`` object is provided, it must
precede the definition of any keyword arguments. For example::

    Lang.nodes.get(
        Q(year=2005) | Q(year=2006),
        name__startswith='Py',
    )

This would be a valid query, equivalent to the previous example;

Has a relationship
==================

The `has` method checks for existence of (one or more) relationships, in this case it returns a set of `Coffee` nodes which have a supplier::

    Coffee.nodes.has(suppliers=True)

This can be negated by setting `suppliers=False`, to find `Coffee` nodes without `suppliers`.

Iteration, slicing and more
===========================

Iteration, slicing and counting is also supported::

    # Iterable
    for coffee in Coffee.nodes:
        print coffee.name

    # Sliceable using python slice syntax
    coffee = Coffee.nodes.filter(price__gt=2)[2:]

The slice syntax returns a NodeSet object which can in turn be chained.

Length and boolean methods dont return NodeSet objects and cannot be chained further::

    # Count with __len__
    print len(Coffee.nodes.filter(price__gt=2))

    if Coffee.nodes:
        print "We have coffee nodes!"

Filtering by relationship properties
====================================

Filtering on relationship properties is also possible using the `match` method. Note that again these relationships must have a definition.::

    coffee_brand = Coffee.nodes.get(name="BestCoffeeEver")

    for supplier in coffee_brand.suppliers.match(since_lt=january):
        print(supplier.name)

Ordering by property
====================

Ordering results by a particular property is done via th `order_by` method::

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

