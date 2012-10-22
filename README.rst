========
NeoModel
========

A high level wrapper around py2neo, providing a formal definition for your data model.

* Structured node definitions with type checking
* Lazy category node creation
* Automatic indexing
* Relationship traversal
* Soft cardinality restrictions

Installation
-------
Install the module via git::

    pip install -e git+git@github.com:robinedwards/neomodel.git@HEAD#egg=neomodel-dev

Introduction
-------

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
        age = IntegerProperty(index=True)

        # traverse outgoing IS_FROM relations, inflate to Country objects
        country = RelationshipTo('Country', 'IS_FROM')

In the above example, there is one type of relationship present `IS_FROM`,
we are defining two different methods for traversing it
one accessible via Person objects and one via Country objects.

CRUD
-------

CReate Update Delete::

    jim = Person(name='Jim', age=3).save()
    jim.age = 4
    jim.save()
    jim.delete()

Relationships
-----
Access related nodes through your defined relations::

    germany = Country(code='DE').save()
    jim.country.connect(germany)

    if jim.country.is_connected(germany):
        print "Jim's from Germany"

    for p in germany.inhabitant.all()
        print p.name # Jim

    jim.country.disconnect(germany)

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
-------
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

Inheritance
-------

*EXPERIMENTAL*

It's possible to subclass node definitions, separate indexes will be
maintained for each class in the hierarchy.

The example below demonstrates the use of class inheritance in relationships::

    # Superhero subclass of Person
    class SuperHero(Person):
        power = StringProperty(index=True)

    # Adding Atlantis to our countries and UltraJoe to our superheroes
    atlantis = Country(code='ATL').save()
    ultrajoe = SuperHero(name='UltraJoe', age=13, power='invisibility').save()

    # Connecting UltraJoe to Atlantis. As a Person (as well a SuperHero),
    # UltraJoe inherits the relationship definitions for Person.
    atlantis.inhabitant.connect(ultrajoe)

    # Checking if connection was indeed made
    atlantis.inhabitant.is_connected(ultrajoe) # True

Relating to different node types
-------

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
-------

Access your instances via the category node::

    country_category = Country.category()
    for c in country_category.instance.all()

Note that `connect` and `disconnect` are not available through the `instance` relation.
As these actions are handled for your via the save() and delete() methods.

Read-only nodes
------

If you have existing nodes you want to protect use the read-only base class::

    from neomodel.core import ReadOnlyNode, ReadOnlyError

    class ImmortalBeing(ReadOnlyNode):
        name = StringProperty()

Now all write operations below raise a *ReadOnlyError*::

    some_immortal_being.delete()
    some_immortal_being.save()
    some_immortal_being.update()

Indexing
-------

Make use of indexes::

    jim = Person.index.get(name='Jim')
    for p in Person.index.search(age=3):
        print p.name

    germany = Country(code='DE').save()

Use advanced Lucene queries with the `lucene-querybuilder` module::

    from lucenequerybuilder import Q

    Human(name='sarah', age=3).save()
    Human(name='jim', age=4).save()
    Human(name='bob', age=5).save()
    Human(name='tim', age=2).save()

    for h in Human.index.search(Q('age', inrange=[3, 5])):
        print h.name

    # prints: sarah, jim, bob

If you have an existing node index you can change the default name of your index.
This can be useful for integrating with neo4django schemas::

    class Human(StructuredNode):
        _index_name = 'myHumans'
        name = StringProperty(indexed=True)

    Human.index.name # myHumans

Properties
---

The following property classes are available::

    StringProperty, IntegerProperty, FloatProperty, BooleanProperty

Credits
-------
* Marianna Polatoglou - https://github.com/mar-chi-pan
* Murtaza Gulamali - https://github.com/mygulamali
* Nigel Small - https://github.com/nigelsmall
* Panos Katseas - https://github.com/pkatseas
