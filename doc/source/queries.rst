================
Advanced queries
================

Neomodel contains an API for querying sets of nodes without needing to write cypher::

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

The `nodes` property on a class is the set of all nodes in the database of that type contained.

This set (or `NodeSet`) can be iterated over and filtered on. Under the hood it uses labels introduced in neo4j 2::

    # nodes with label Coffee whose price is greater than 2
    Coffee.nodes.filter(price__gt=2)

    try:
        java = Coffee.nodes.get(name='Java')
    except Coffee.DoesNotExist:
        print "Couldn't find coffee 'Java'"

The filter method borrows the same django filter format with double underscore prefixed operators:

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

Has a relationship
==================

The `has` method checks for existence of (one or more) relationships, in this case it returns a set of `Coffee` nodes which have a supplier::

    Coffee.nodes.has(suppliers=True)

This can be negated `suppliers=False`, should you wish to find `Coffee` nodes without `suppliers`.

Iteration, slicing and more
===========================

Iteration, slicing and counting is also supported::

    # Iterable
    for coffee in Coffee.nodes:
        print coffee.name

    # Sliceable using python slice syntax
    coffee = Coffee.nodes.filter(price__gt=2)[2:]

The slice syntax returns a NodeSet object which can in turn be chained.

Length and boolean methods dont return NodeSet objects so cant be chained further::

    # Count with __len__
    print len(Coffee.nodes.filter(price__gt=2))

    if Coffee.nodes:
        print "We have coffee nodes!"

Filtering by relationship properties
====================================

Filtering on relationship properties is also possible using the `match` method. Note that again these relationships must have a definition.::

    nescafe = Coffee.nodes.get(name="Nescafe")

    for supplier in nescafe.suppliers.match(since_lt=january):
        print supplier.name

Ordering by property
====================

To order results by a particular property, use the `order_by` method::

    # Ascending sort
    for coffee in Coffee.nodes.order_by('price'):
        print coffee, coffee.price

    # Descending sort
    for supplier in Supplier.nodes.order_by('-delivery_cost'):
        print supplier, supplier.delivery_cost


To remove ordering from a previously defined query, pass `None` to `order_by`::

    # Sort in descending order
    suppliers = Supplier.nodes.order_by('-delivery_cost')

    # Don't order; yield nodes in the order neo4j returns them
    suppliers = suppliers.order_by(None)
