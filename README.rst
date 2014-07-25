.. image:: https://raw.github.com/robinedwards/neomodel/master/art/neomodel-300.png
   :alt: neomodel

An Object Graph Mapper (OGM) for the neo4j_ graph database.

Don't need an OGM? Try the awesome py2neo_ (which this library is built on).

.. _py2neo: http://www.py2neo.org
.. _neo4j: http://www.neo4j.org

Supports: neo4j 2.0+ python 2.7, 3.3

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

We can use the `Relationship` class if we don't want to specify a direction.

Create, save delete etc::

    jim = Person(name='Jim', age=3).save()
    jim.age = 4
    jim.save() # validation happens here
    jim.delete()
    jim.refresh() # reload properties from neo

Using relationships::

    germany = Country(code='DE').save()
    jim.country.connect(germany)

    if jim.country.is_connected(germany):
        print("Jim's from Germany")

    for p in germany.inhabitant.all()
        print(p.name) # Jim

    len(germany.inhabitant) # 1

    # Find people called 'Jim' in germany
    germany.inhabitant.search(name='Jim')

    jim.country.disconnect(germany)

Relationship models, define your relationship properties::

    class FriendRel(StructuredRel):
        since = DateTimeProperty(default=lambda: datetime.now(pytz.utc))
        met = StringProperty()

    class Person(StructuredNode):
        name = StringProperty()
        friends = RelationshipTo('Person', 'FRIEND', model=FriendRel)

    rel = jim.friend.connect(bob)
    rel.since # datetime object

You can specify the properties during connect::

    rel = jim.friend.connect(bob, {'since': yesterday, 'met': 'Paris'})

    print(rel.start_node().name) # jim
    print(rel.end_node().name) # bob

    rel.met = "Amsterdam"
    rel.save()

You can retrieve relationships between to nodes using the 'relationship' method.
This is only available for relationships with a defined structure::

    rel = jim.friend.relationship(bob)

Directionless relationships::

    class Person(StructuredNode):
        friends = Relationship('Person', 'FRIEND')

When defining relationships, you may refer to classes in other modules.
This helps avoid cyclic imports::

    class Garage(StructuredNode):
        cars = RelationshipTo('transport.models.Car', 'CAR')
        vans = RelationshipTo('.models.Van', 'VAN')

When defining models that have custom `__init__(self, ...)` function, don't
forget to call `super()`. Otherwise things start to fail::

    class Person(StructuredNode):
        name = StringProperty(unique_index=True)

        def __init__(self, name, **args):
            self.name = name

            super(Person, self).__init__(self, **args)

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
            results, columns = self.cypher("START a=node({self}) MATCH a-[:FRIEND]->(b) RETURN b")
            return [self.__class__.inflate(row[0]) for row in results]

    # for standalone queries
    from neomodel import db
    db.cypher_query(query, params)
    # TODO - inflate example

The self query parameter is prepopulated with the current node id. It's possible to pass in your
own query parameters to the cypher method.

You may log queries by setting the environment variable `NEOMODEL_CYPHER_DEBUG` to true.

Batch create
------------
Atomically create multiple nodes in a single operation::

    people = Person.create(
        {'name': 'Tim', 'age': 83},
        {'name': 'Bob', 'age': 23},
        {'name': 'Jill', 'age': 34},
    )

This is useful for creating large sets of data. It's worth experimenting with the size of batches
to find the optimum performance suggestions on size around 300 - 500.


Hooks and Signals
-----------------
You may define the following hook methods on your nodes::

    pre_save, post_save, pre_delete, post_delete, post_create

Signals are also supported *if* django is available::

    from django.db.models import signals
    signals.post_save.connect(your_func, sender=Person)

Transactions
------------
transactions can be used via a function decorator or context mangaer::

    with db.transaction:
        Person(name='Bob').save()

    @db.transaction
    def update_user_name(uid, name):
        user = Person.nodes.filter(uid=uid)[0]
        user.name = name
        user.save()

Indexing - DEPRECATED
---------------------
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
        print(h.name)

    # prints: sarah, jim, bob

Or use lucene query syntax directly::

    Human.index.search("age:4")

Specify a custom index name for a class (inherited). Be very careful when sharing indexes
between classes as this means nodes will inflated to any class sharing the index.
Properties of the same name on different classes may conflict.::

    class Badger(StructuredNode):
        __index__ = 'MyBadgers'
        name = StringProperty(unique_index=True)

Properties
----------
The following properties are available::

    StringProperty, IntegerProperty, FloatProperty, BooleanProperty, ArrayProperty

    DateProperty, DateTimeProperty, JSONProperty, AliasProperty

The *DateTimeProperty* accepts datetime.datetime objects of any timezone and stores them as a UTC epoch value.
These epoch values are inflated to datetime.datetime objects with the UTC timezone set. If you want neomodel
to raise an exception on receiving a datetime without a timezone you set the env var NEOMODEL_FORCE_TIMEZONE=1.

The *DateProperty* accepts datetime.date objects which are stored as a string property 'YYYY-MM-DD'.

*Default values* you may provide a default value to any property, this can also be a function or any callable::

        from uuid import uuid4
        my_id = StringProperty(unique_index=True, default=uuid4)

You may provide arguments using a wrapper function or lambda::

        my_datetime = DateTimeProperty(default=lambda: datetime.now(pytz.utc))

The *AliasProperty* a special property for aliasing other properties and providing 'magic' behaviour::

    class Person(StructuredNode):
        full_name = StringProperty(index=True)
        name = AliasProperty(to='full_name')

    Person.index.search(name='Jim') # just works
