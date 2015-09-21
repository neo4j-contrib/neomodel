=============
Relationships
=============

Directionless relationships::

    class Person(StructuredNode):
        friends = Relationship('Person', 'FRIEND')

When defining relationships, you may refer to classes in other modules.
This avoids cyclic imports::

    class Garage(StructuredNode):
        cars = RelationshipTo('transport.models.Car', 'CAR')
        vans = RelationshipTo('.models.Van', 'VAN')

Cardinality
===========
It's possible to (softly) enforce cardinality restrictions on your relationships.
Remember this needs to be declared on both sides of the definition::

    class Person(StructuredNode):
        car = RelationshipTo('Car', 'CAR', cardinality=One)

    class Car(StructuredNode):
        owner = RelationshipFrom('Person', cardinality=One)

The following cardinality classes are available::

    ZeroOMore (default), OneOrMore, ZeroOrOne, One

If cardinality is broken by existing data a *CardinalityViolation* exception is raised.
On attempting to break a cardinality restriction a *AttemptedCardinalityViolation* is raised.

Properties
==========

Neomodel uses relationship models to define the properties stored on relations::

    class FriendRel(StructuredRel):
        since = DateTimeProperty(default=lambda: datetime.now(pytz.utc))
        met = StringProperty()

    class Person(StructuredNode):
        name = StringProperty()
        friends = RelationshipTo('Person', 'FRIEND', model=FriendRel)

    rel = jim.friends.connect(bob)
    rel.since # datetime object

These can be passed in when calling the connect method::

    rel = jim.friends.connect(bob, {'since': yesterday, 'met': 'Paris'})

    print(rel.start_node().name) # jim
    print(rel.end_node().name) # bob

    rel.met = "Amsterdam"
    rel.save()

You can retrieve relationships between two nodes using the 'relationship' method.
This is only available for relationships with a defined relationship model::

    rel = jim.friends.relationship(bob)

Explicit Traversal
==================

It is possible to specify a node traversal by creating a Traversal object. This will get all Person entities that are
directly related to another Person, through all relationships::

    definition = dict(node_class=Person, direction=OUTGOING, relation_type=None, model=None)
    relations_traversal = Traversal(jim, Person.__label__, definition)
    all_jims_relations = relations_traversal.all()

- node class: the type of the relationship target
- direction: OUTGOING/INCOMING/EITHER
- realtion_type: can be None (any direct), '*' for all paths or an explicit name of the relationship type.
- model: the tpye of the model object, None for simple relationship
