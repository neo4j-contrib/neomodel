.. image:: https://raw.github.com/robinedwards/neomodel/master/art/neomodel-300.png
   :alt: neomodel

An Object Graph Mapper (OGM) for the neo4j_ graph database.

Don't need an OGM? Try the awesome py2neo_ (which this library is built on).

.. _py2neo: http://www.py2neo.org
.. _neo4j: http://www.neo4j.org

Supports: neo4j 1.8+ (1.9 recommended), python 2.7, 3.3

.. image:: https://secure.travis-ci.org/robinedwards/neomodel.png
   :target: https://secure.travis-ci.org/robinedwards/neomodel/

The basics
----------
Set the location of neo4j via an environment variable (default is http://localhost:7474/db/data/)::

    export NEO4J_REST_URL=http://user:password@localhost:7474/db/data/

In the example below, there is one type of relationship present `IS_FROM`,
we are defining two different ways for traversing it
one accessible via Person objects and one via Country objects::

    from neomodel import (StructuredNode, StringProperty, IntegerProperty,
        RelationshipTo, RelationshipFrom)

    class Country(StructuredNode):
        code = StringProperty(unique_index=True, required=True)

        # traverse incoming IS_FROM relation, inflate to Person objects
        inhabitant = RelationshipFrom('Person', 'IS_FROM')


    class Person(StructuredNode):
        name = StringProperty(unique_index=True)
        age = IntegerProperty(index=True, default=0)

        # traverse outgoing IS_FROM relations, inflate to Country objects
        country = RelationshipTo(Country, 'IS_FROM')

Create, save delete etc::

    jim = Person(name='Jim', age=3).save()
    jim.age = 4
    jim.save() # validation happens here
    jim.delete()
    jim.refresh() # reload properties from neo

Batch create (atomic) which also validates and indexes::

    people = Person.create(
        {'name': 'Tim', 'age': 83},
        {'name': 'Bob', 'age': 23},
        {'name': 'Jill', 'age': 34},
    )

Using relationships::

    germany = Country(code='DE').save()
    jim.country.connect(germany)

    if jim.country.is_connected(germany):
        print("Jim's from Germany")

    for p in germany.inhabitant.all()
        print(p.name) # Jim

    len(germany.inhabitant) # 1

    jim.country.disconnect(germany)

You can also add properties when creating relationships, for example the
previous code could be::

    jim.country.connect(germany, {'arrived': '10/12/2012'})

Search related nodes. This example starts at the germany node
and traverses incoming 'IS_FROM' relations and returns the nodes with the property name
that is equal to 'Jim'::

    germany.inhabitant.search(name='Jim')

If you don't care about the direction of the relationship::

    class Person(StructuredNode):
        friends = Relationship('Person', 'FRIEND')

You may also reference classes from another module::

    class Person(StructuredNode):
        car = RelationshipTo('transport.models.Car', 'CAR')

Traversals - EXPERIMENTAL
-------------------------
The argument for the traverse method is the name of the relationship manager on the class,
in this example we traverse the friends relationship skipping the first and limit to 10 nodes::

    # query executes on iteration
    for friend in jim.traverse('friends').order_by_desc('age').skip(1)limit(10):
        print friend.name

You can traverse as many levels as you like, run() executes the query::

    # order by country name
    results = jim.traverse('friends').traverse('country').order_by('name').run()

    # or friends name
    jim.traverse('friends').traverse('country').order_by('friends.name')

Filtering by node properties also works::

    results = jim.traverse('friends').where('age', '>', 18).run()

length and bool operations work as expected::

    print "Jim has " + len(jim.traverse('friends') + " friends"

Category nodes
--------------
Access all your instances of a class via the category node::

    country_category = Country.category()
    for c in country_category.instance.all()

Note that `connect` and `disconnect` are not available through the `instance` relation.

Cardinality
-----------
It's possible to enforce cardinality restrictions on your relationships.
Remember this needs to be declared on both sides of the relationship for it to work::

    class Person(StructuredNode):
        car = RelationshipTo('Car', 'CAR', cardinality=One)

    class Car(StructuredNode):
        owner = RelationshipFrom('Person', cardinality=One)

The following cardinality classes are available::

    ZeroOMore (default), OneOrMore, ZeroOrOne, One

If cardinality is broken by existing data a *CardinalityViolation* exception is raised.
On attempting to break a cardinality restriction a *AttemptedCardinalityViolation* is raised.

Cypher queries
--------------
You may handle more complex queries via cypher. Each node provides an 'inflate' class method,
this inflates py2neo nodes to neomodel node objects::

    class Person(StructuredNode):
        def friends(self):
            results, metadata = self.cypher("START a=node({self}) MATCH a-[:FRIEND]->(b) RETURN b");
            return [self.__class__.inflate(row[0]) for row in results]

The self query parameter is prepopulated with the current node id. It's possible to pass in your
own query parameters to the cypher method.


Relating to many node types
--------------------------------
You can define relations of a single type to different `StructuredNode` classes.::

    class Humanbeing(StructuredNode):
        name = StringProperty()
        has_a = RelationshipTo(['Location', 'Nationality'], 'HAS_A')

    class Location(StructuredNode):
        name = StringProperty()

    class Nationality(StructuredNode):
        name = StringProperty()

Remember that when traversing the `has_a` relation you will retrieve objects of different types.

Hooks and Signals
-----------------
You may define the following hook methods on your nodes::

    pre_save, post_save, pre_delete, post_delete, post_create

Signals are also supported *if* django is available::

    from django.db.models import signals
    signals.post_save.connect(your_func, sender=Person)


Indexing
--------
Make use of indexes::

    jim = Person.index.get(name='Jim')
    for p in Person.index.search(age=3):
        print(p.name)

    germany = Country(code='DE').save()

Use advanced Lucene queries with the `lucene-querybuilder` module::

    from lucenequerybuilder import Q

    Human(name='sarah', age=3).save()
    Human(name='jim', age=4).save()
    Human(name='bob', age=5).save()
    Human(name='tim', age=2).save()

    for h in Human.index.search(Q('age', inrange=[3, 5])):
        print(h.name) # sarah, jim, bob

Or as a lucene query string::

    sarah = Human.index.search('name:sar*')

Properties
----------
The following properties are available::

    StringProperty, IntegerProperty, FloatProperty, BooleanProperty

    DateProperty, DateTimeProperty, JSONProperty, AliasProperty

The *DateTimeProperty* accepts datetime.datetime objects of any timezone and stores them as a UTC epoch value.
These epoch values are inflated to datetime.datetime objects with the UTC timezone set.

The *DateProperty* accepts datetime.date objects which are stored as a string property 'YYYY-MM-DD'.

*Default values* you may provide a default value to any property, this can also be a function or any callable::

        from uuid import uuid4
        my_id = StringProperty(unique_index=True, default=uuid4)

The *AliasProperty* a special property for aliasing other properties and providing 'magic' behaviour::

    class Person(StructuredNode):
        full_name = StringProperty(index=True)
        name = AliasProperty(to='full_name')

    Person.index.search(name='Jim') # just works
