========
NeoModel
========

A high level wrapper around py2neo, providing a formal definition for your data model.

* Structured node definitions with type checking
* Lazy category node creation
* Automatic indexing
* Simple relationship traversal
* Soft cardinality restrictions

============
Installation
============

Install the module via git::

    pip install -e git+git@github.com:robinedwards/neomodel.git@HEAD#egg=neomodel-dev

============
Introduction
============

Connection::

    export NEO4J_URL=http://localhost:7474/db/data/

Node definitions::

    from neomodel import StructuredNode, StringProperty, IntegerProperty

    class Country(StructuredNode):
        code = StringProperty(unique_index=True)


    class Person(StructuredNode):
        name = StringProperty(unique_index=True)
        age = IntegerProperty(index=True)

Define relationships between your models::

    # defines relation of type IS_FROM from Person to Country nodes
    Person.outgoing('IS_FROM', alias='is_from', to=Country)
    # traverse incoming IS_FROM relations on Country via the inhabitants property
    Country.incoming('IS_FROM', alias='inhabitant', to=Person)

An alias is just a name given to a relationship, in order to have access to it
via python objects. In the above example, there is only one neo4j relationship
present (IS_FROM), we are just defining two different aliases for it, one
accessible via the Person objects and one via Country objects. All objects of
class Person can access that relationship through the *is_from* attribute,
and all objects of class Country can access it through the *inhabitant* attribute.

The *to* field respects Class inheritance. You can specify an abstract class
or superclass and maintain the defined relationship for all its subclasses.

Access related nodes through your defined relations::

    germany = Country(code='DE').save()
    jim.is_from.connect(germany)

    if jim.is_from.is_connected(germany):
        print "Jim's from Germany"

    for p in germany.inhabitant.all()
        print p.name # Jim

    jim.is_from.disconnect(germany)

And an example showcasing Class inheritance in relatioships::

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

CReate Update Delete::

    jim = Person(name='Jim', age=3).save()
    jim.age = 4
    jim.update()
    jim.delete()

========
Indexing
========

Make use of indexes::

    jim = Person.index.get(name='Jim')
    for p in Person.index.search(age=3):
        print p.name

    germany = Country(code='DE').save()

Use advanced lucene queries::

    from lucenequerybuilder import Q

    Human(name='sarah', age=3).save()
    Human(name='jim', age=4).save()
    Human(name='bob', age=5).save()
    Human(name='tim', age=2).save()

    for h in Human.index.search(Q('age', inrange=[3, 5])):
        print h.name

    # prints: sarah, jim, bob

=======
Credits
=======
* Nigel Small - https://github.com/nigelsmall
* Murtaza Gulamali - https://github.com/mygulamali
* Marianna Polatoglou - https://github.com/mar-chi-pan
* Panos Katseas - https://github.com/pkatseas
