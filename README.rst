========
NeoModel
========

Strict definitions for your nodes, a py2neo wrapper.

============
Introduction
============
Node definitions::

    from neomodel.core import NeoNode, StringProperty, IntegerProperty, relate

    class Country(NeoNode):
        code = StringProperty(unique_index=True)


    class Person(NeoNode):
        name = StringProperty(unique_index=True)
        age = IntegerProperty(index=True)

Deploy category nodes for defined models::

    Country.deploy()
    Person.deploy()

Define relationships between your models::

    # defines relation of type IS_FROM from Person to Country nodes
    # traverse incoming IS_FROM relations on Country via the inhabitants property
    relate(Person, 'is_from', Country, 'inhabitants')

Access related nodes through your defined relations::

    germany = Country(code='DE').save()
    jim.is_from.relate(germany)

    if jim.is_from.is_related(germany):
        print "Jim's from Germany"

    for p in germany.inhabitants.all()
        print p.name # Jim

    jim.is_from.unrelate(germany)

CReate Update Delete::

    jim = Person(name='Jim', age=3).save()
    jim.age = 4
    jim.update()
    jim.delete()

Make use of the lucene indexes::

    jim = Person.index.get(name='Jim')
    for p in Person.index.search(age=3):
        print p.name

    germany = Country(code='DE').save()
