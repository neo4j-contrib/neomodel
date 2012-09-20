========
NeoModel
========

Strict definitions for your nodes, a py2neo wrapper.

============
Introduction
============
Node definitions::

    from neomodel import NeoNode, StringProperty, IntegerProperty, OUTGOING, INCOMING

    class Country(NeoNode):
        code = StringProperty(unique_index=True)


    class Person(NeoNode):
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
