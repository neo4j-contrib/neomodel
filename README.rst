========
NeoModel
========

Model like definitions for neo4j, a py2neo wrapper.

=======
Example
=======
Boring example::

    from neomodel.core import NeoNode, StringProperty, IntegerProperty, Relationship

    class Country(NeoNode):
        code = StringProperty(unique_index=True)


    class Person(NeoNode):
        name = StringProperty(unique_index=True)
        age = IntegerProperty(index=True)
        is_from = Relationship('IS_FROM', Country)

    # Deploy category nodes to your db.
    Country.deploy()
    Person.deploy()

    # Create a person
    jim = Person(name='Jim', age=3).save()

    # find someone via index
    jim = Person.get(name='Jim')

    # search for many
    people = Person.search(age=3)

    germany = Country(code='DE').save()
    # create and destroy relationships
    jim.is_from.relate(germany)
    jim.is_from.unrelate(germany)


