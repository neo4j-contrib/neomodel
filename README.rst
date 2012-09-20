========
NeoModel
========

A high level wrapper around to py2neo, providing formal definitions for your data model.

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
Node definitions::

    from neomodel import StructuredNode, StringProperty, IntegerProperty, OUTGOING, INCOMING

    class Country(StructuredNode):
        code = StringProperty(unique_index=True)


    class Person(StructuredNode):
        name = StringProperty(unique_index=True)
        age = IntegerProperty(index=True)

Define relationships between your models::

    # defines relation of type IS_FROM from Person to Country nodes
    Person.relate('is_from', (OUTGOING, 'IS_FROM'), to=Country)
    # traverse incoming IS_FROM relations on Country via the inhabitants property
    Country.relate('inhabitant', (INCOMING, 'IS_FROM'), to=Person)

Access related nodes through your defined relations::

    germany = Country(code='DE').save()
    jim.is_from.connect(germany)

    if jim.is_from.is_connected(germany):
        print "Jim's from Germany"

    for p in germany.inhabitants.all()
        print p.name # Jim

    jim.is_from.disconnect(germany)

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
Nigel Small - https://github.com/nigelsmall
Murtaza Gulamali - https://github.com/mygulamali
Your Name Here...
