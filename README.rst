.. image:: https://raw.github.com/robinedwards/neomodel/master/art/neomodel-300.png
   :alt: neomodel

An object mapper for the neo4j graph database.

* Structured node definitions with type checking
* Automatic indexing and categorising
* Relationship traversal
* Soft cardinality restrictions
* pre and post save / delete hooks (and django signals!)

Supports: neo4j 1.8+ (1.9 recommended), python 2.6, 2.7

.. image:: https://secure.travis-ci.org/robinedwards/neomodel.png
   :target: https://secure.travis-ci.org/robinedwards/neomodel/

Introduction
------------

Connection::

    export NEO4J_REST_URL=http://localhost:7474/db/data/

Or with authentication::

    export NEO4J_REST_URL=http://user:password@localhost:7474/db/data/

Node definitions::

    from neomodel import StructuredNode, StringProperty, IntegerProperty, RelationshipTo, RelationshipFrom
    class Country(StructuredNode):
        code = StringProperty(unique_index=True, required=True)

        # traverse incoming IS_FROM relation, inflate to Person objects
        inhabitant = RelationshipFrom('Person', 'IS_FROM')


    class Person(StructuredNode):
        name = StringProperty(unique_index=True)
        age = IntegerProperty(index=True, default=0)

        # traverse outgoing IS_FROM relations, inflate to Country objects
        country = RelationshipTo('Country', 'IS_FROM')

In the above example, there is one type of relationship present `IS_FROM`,
we are defining two different methods for traversing it
one accessible via Person objects and one via Country objects.

CRUD
----

CReate Update Delete::

    jim = Person(name='Jim', age=3).save()
    jim.age = 4
    jim.save() # validation happens here
    jim.delete()
    jim.refresh() # reload properties if node exists, otherwise raises DoesNotExist

Batch create (atomic) which also validates and indexes::

    people = Person.create(
        {'name': 'Tim', 'age': 83},
        {'name': 'Bob', 'age': 23},
        {'name': 'Jill', 'age': 34},
    )

Hooks and Signals
-----------------
You may define the following hook methods on your nodes::

    pre_save, post_save, pre_delete, post_delete, post_create

Signals are also supported *if* django is available::

    from django.db.models import signals
    signals.post_save.connect(your_func, sender=Person)

Relationships
-------------
Access related nodes through your defined relations::

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

    jim.country.connect(germany, properties={'city': 'Munich'})

or::

    jim.country.connect(germany, {'city': 'Munich'})

Search related nodes through your defined relations. This example starts at the germany node
and traverses incoming 'IS_FROM' relations and returns the nodes with the property name
that is equal to 'Jim'::

    germany.inhabitant.search(name='Jim')

If you don't care about the direction of the relationship::

    class Person(StructuredNode):
        friends = Relationship('Friend', 'FRIEND')

You may also reference classes from another module::

    class Person(StructuredNode):
        car = RelationshipTo('transport.models.Car', 'CAR')

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

Custom cypher queries
---------------------

You may handle more complex queries via cypher. Each node provides an 'inflate' class method,
this inflates py2neo nodes to neomodel node objects::

    class Person(StructuredNode):
        def friends(self):
            results = self.cypher("START a=node({self}) MATCH a-[:FRIEND]->(b) RETURN b");
            return [self.__class__.inflate(row[0]) for row in results]

The self query parameter is prepopulated with the current node id. It's possible to pass in your
own query parameters to the cypher method.


Relating to different node types
--------------------------------

You can define relations of a single relation type to different `StructuredNode` classes.::

    class Humanbeing(StructuredNode):
        name = StringProperty()
        has_a = RelationshipTo(['Location', 'Nationality'], 'HAS_A')

    class Location(StructuredNode):
        name = StringProperty()

    class Nationality(StructuredNode):
        name = StringProperty()

Remember that when traversing the `has_a` relation you will retrieve objects of different types.


Category nodes
--------------

Access your instances via the category node::

    country_category = Country.category()
    for c in country_category.instance.all()

Note that `connect` and `disconnect` are not available through the `instance` relation.

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
        print(h.name)

    # prints: sarah, jim, bob

Properties
----------

The following basic properties are available::

    StringProperty, IntegerProperty, FloatProperty, BooleanProperty

Additionally there is also::

    DateProperty, DateTimeProperty, AliasProperty

The *DateTimeProperty* accepts datetime.datetime objects of any timezone and stores them as a UTC epoch value.

These epoch values are inflated to datetime.datetime objects with the UTC timezone set.

The *DateProperty* accepts datetime.date objects which are stored as a string property 'YYYY-MM-DD'.


*Default values* you may provide a default value to any property, this can also be a function or any callable::

        def uid_generator():
            # your algorithm here
            pass

        name = StringProperty(unique_index=True, default=uid_generator)

The *AliasProperty* a special property for aliasing other properties and providing 'magic' behaviour::

    class Person(StructuredNode):
        full_name = StringProperty(index=True)
        name = AliasProperty(to='full_name')

    Person.index.search(name='Jim') # just works

Custom properties can provide a setup method which will get invoked on class definition.
