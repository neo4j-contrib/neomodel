=============
Relationships
=============

Establishing an undirected relationship between two entities is done via the `Relationship` 
class. This requires the class of the connected entity as well as the type of the relationship.::

    class Person(StructuredNode):
        friends = Relationship('Person', 'FRIEND')

When defining relationships, you may refer to classes in other modules.
This avoids cyclic imports::

    class Garage(StructuredNode):
        cars = RelationshipTo('transport.models.Car', 'CAR')
        vans = RelationshipTo('.models.Van', 'VAN')

Cardinality
===========
It is possible to (softly) enforce cardinality constraints on your relationships.
Remember this needs to be declared on both sides of the relationship definition::

    class Person(StructuredNode):
        car = RelationshipTo('Car', 'OWNS', cardinality=One)

    class Car(StructuredNode):
        owner = RelationshipFrom('Person', 'OWNS', cardinality=One)

The following cardinality constraints are available:

===================================================  ========================================
:class:`~neomodel.cardinality.ZeroOrOne`             :class:`~neomodel.cardinality.One`
:class:`~neomodel.cardinality.ZeroOrMore` (default)  :class:`~neomodel.cardinality.OneOrMore`
===================================================  ========================================

If a cardinality constrain is violated by existing data a :class:`~neomodel.exception.CardinalityViolation`
exception is raised.

On attempting to violate a cardinality constrain a 
:class:`~neomodel.exception.AttemptedCardinalityViolation` is raised.

Properties
==========

Neomodel uses :mod:`~neomodel.relationship` models to define the properties stored on relations::

    class FriendRel(StructuredRel):
        since = DateTimeProperty(
            default=lambda: datetime.now(pytz.utc)
        )
        met = StringProperty()

    class Person(StructuredNode):
        name = StringProperty()
        friends = RelationshipTo('Person', 'FRIEND', model=FriendRel)

    rel = jim.friends.connect(bob)
    rel.since # datetime object


The data to populate these properties when establishing a connection can be supplied 
to the ``connect`` method::

    rel = jim.friends.connect(bob,
                              {'since': yesterday, 'met': 'Paris'})

    print(rel.start_node().name) # jim
    print(rel.end_node().name) # bob

    rel.met = "Amsterdam"
    rel.save()

You can retrieve relationships between two nodes using the 'relationship' method.
This is only available for relationships with a defined relationship model::

    rel = jim.friends.relationship(bob)

Relationship Uniqueness
=======================

By default neomodel applies only one relationship instance between two node instances and 
this is achieved via use of ``MERGE``. (This used to be ``CREATE UNIQUE`` until Cypher deprecated this command.)

Relationships and Inheritance
=============================

Relationships are established between Nodes of different types within a Neo4J Data Base Management System (DBMS) and
this section contains more details about how nodes of different types at the two endpoints of a relationship
are resolved by neomodel as wel as how extending relationship classes themselves works.

.. _node_inheritance:

Node Inheritance
----------------
Neomodel is capable of understanding and resolving derived nodes at the endpoints of a relationships properly.

The following model establishes a ``BasePerson`` that can be `friends_with` any class derived
from ``BasePerson``. Two concrete classes of ``BasePerson`` (``TechnicalPerson`` and ``PilotPerson``) are
further defined. ::


    class PersonalRelationship(neomodel.StructuredRel):
        """
        A very simple relationship between two BasePersons that simply 
        records the date at which an acquaintance was established.
        """
        on_date = neomodel.DateProperty(default_now = True)
        
    class BasePerson(neomodel.StructuredNode):
        """
        Base class for defining some basic sort of an actor in a system.
        
        The base actor is defined by its name and a `friends_with` 
        relationship.
        """
        name = neomodel.StringProperty(required = True, unique_index = True)
        friends_with = neomodel.RelationshipTo("BasePerson", "FRIENDS_WITH", model = PersonalRelationship)
        
    class TechnicalPerson(BasePerson):
        """
        A Technical person specialises BasePerson by adding their 
        expertise.
        """
        expertise = neomodel.StringProperty(required = True)
        
    class PilotPerson(BasePerson):
        """
        A pilot person specialises BasePerson by adding the type of 
        airplane they can operate.
        """
        airplane = neomodel.StringProperty(required = True)
        
This means that either of these concrete objects can appear at the end 
of a ``friends_with`` relationship and be instantiated to the right object.

Here is a minimal example to demonstrate that::

    # Create some technical persons
    A = TechnicalPerson(name = "Grumpy", expertise = "Grumpiness").save()
    B = TechnicalPerson(name = "Happy", expertise = "Unicorns"}).save()
    C = TechnicalPerson(name = "Sleepy", expertise = "Pillows"}).save()
    
    # Create some Pilot Persons
    D = PilotPerson(name = "Porco Rosso", airplane = "Savoia-Marchetti").save()
    E = PilotPerson(name = "Jack Dalton", airplane = "Beechcraft Model 18").save()
    
    # TechnicalPersons befriend Technical Persons
    A.friends_with.connect(B)
    B.friends_with.connect(C)
    C.friends_with.connect(A)
    
    # Pilot Persons befriend Pilot Persons
    D.friends_with.connect(E)
    
    # Technical Persons befriend Pilot Persons
    A.friends_with.connect(D)
    E.friends_with.connect(C)
    
    for some_friend in A.friends_with:
        print(some_friend)
        
This will show two friends connected with node "Grumpy", one of which is a ``TechnicalPerson`` 
and the other a ``PilotPerson``.


Relationship Inheritance
------------------------

Neomodel uses ``StructuredRel`` to create classes that describe relationship objects. When the time comes to store this
relationship with the DBMS, neomodel creates a Neo4J Relationship that is characterised by a **single label** along with
the data members of the relationship class. Therefore, there is a direct correspondence between the relationship label
and the relationship class.

Continuing with the example that is defined in section :ref:`node_inheritance`, it is possible to extend
``PersonalRelationship`` to describe extended (or enriched) versions of the same class, in this way::


    class PersonalRelationshipWithStrength(PersonalRelationship):
        """
        An extended relationship between two BasePersons that in addition to the date on which the acquaintance was
        established, it also maintains an abstract `strength` value.
        """
        on_date = neomodel.DateProperty(default_now = True)
        strength = neomodel.FloatProperty(default = 1.0)

There is nothing too special here about the way ``PersonalRelationshipWithStrength`` is established, except perhaps
noticing that it inherits from ``PersonalRelationship`` rather than ``neomodel.StructuredRel``.

The *special* bit however comes when the extended relationship is attempted to be declared between two nodes. To
demonstrate this here, we will extend ``BasePerson`` and constrain its ``friends_with`` attribute to be of type
``PersonalRelationshipWithStrength``::

    class ExtendedBasePerson(BasePerson):
        """
        An additional actor in a system, characterised further by a `role` attribute and having relationships with a
        `strength` attribute.
        """
        name = neomodel.StringProperty(required = True, unique_index = True)
        role = neomodel.StringProperty(required = True)
        friends_with = neomodel.RelationshipTo("BasePerson", "FRIENDS_WITH", model = PersonalRelationshipWithStrength)

In this case, ``ExtendedBasePerson`` entities are expected to have relationships with a ``strength`` attribute. At the
moment, ``PersonalRelationshipWithStrength`` substitutes ``PersonalRelationship`` entirely everywhere within the data
model. This is in-line with Neo4Js current capabilities of supporting only one label per relationship.

Since relationship classes are "tied" to their label definition, derived relationships can only be attached to the same
label. In the above example, ``FRIENDS_WITH`` is already "tied" to relationships of type ``PersonalRelationship`` and
``PersonalRelationshipWithStrength`` derives from ``PersonalRelationship`` and this kind of relationship class extension
is permissible.

If a relationship label is already "tied" with a relationship model and an attempt is made to re-associate it with an
entirely alien relationship class, an exception of type ``neomodel.exceptions.RelationshipClassRedefined`` is raised
that contains full information about the current data model state and the re-definition attempt.

This now enables queries returning ``Relationship`` objects to be instantiated to their proper models. Continuing with
the above example, a representative query to demonstrate this capability would be::

    Z = neomodel.db.cypher_query("MATCH (:BasePerson)-[r:FRIENDS_WITH]->(:BasePerson) RETURN r", resolve_objects=True)

Notice here that ``resolve_objects`` is set to ``True``, which enables this automatic resolution of returned objects
to their "local" data model counterparts.

Now, elements of ``Z`` contain properly instantiated relationship objects. And because of this, it is now possible to
access the nodes at their end points directly. For example::

    u = Z[0][0][0].start_node()
    v = Z[0][0][0].end_node()

Here, ``u,v`` will be instantiated to whatever type nodes are expected to be found at the end points of the
relationship.

It is worth mentioning at this point that attempting to instantiate a relationship that has not been made known to
neomodel leads to an exception. For example, suppose that the DBMS contains relationships with label ``BUDDIES_WITH``
in addition to what has already been defined earlier as ``FRIENDS_WITH``. If that relationship is attempted to be
"ingested" by neomodel, then exception ``RelationshipClassNotDefined`` would be raised::

    Z = neomodel.db.cypher_query("MATCH (:BasePerson)-[r:BUDDIES_WITH]->(:BasePerson) RETURN r", resolve_objects=True)


Explicit Traversal
==================

It is possible to specify a node traversal by creating a
:class:`~neomodel.match.Traversal` object. This will get all ``Person`` entities
that are directly related to another ``Person``, through all relationships::

    definition = dict(node_class=Person, direction=OUTGOING,
                      relation_type=None, model=None)
    relations_traversal = Traversal(jim, Person.__label__,
                                    definition)
    all_jims_relations = relations_traversal.all()

The ``defintion`` argument is a :term:`py3:mapping` with these items:

=================  ===============================================================
``node_class``     The class of the traversal target node.
``direction``      ``match.OUTGOING`` / ``match.INCOMING`` / ``match.EITHER``
``relation_type``  Can be ``None`` (for any direction), ``*`` for all paths
                   or an explicit name of a relation type (the edge's label).
``model``          The class of the relation model, ``None`` for such without one.
=================  ===============================================================
