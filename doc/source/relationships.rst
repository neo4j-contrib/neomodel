=============
Relationships
=============

Establishing an undirected relationship between two entities is done via the `Relationship` 
class. This requires the class of the connected entity as well as the type of the relationship.

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
to the `connect` method::

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
this is achieved via use of `CREATE UNIQUE`.

Relationships and Inheritance
=============================
Neomodel is capable of understanding and resolving inheritance relationships properly.

The following model establishes a BasePerson that can be `friends_with` any class derived 
from BasePerson. Two concrete classes of BasePerson (TechnicalPerson and PilotPerson) are 
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


Automatic class resolution
--------------------------

Neomodel is able to transform nodes to objects, automatically, via a *node-class registry* 
that is progressively built up during the definition of the models.

The dictionary provides a mapping from the set of labels associated with a node to the class 
that is implied by this set of labels. In the example above, the *node-class registry* would contain 
the following entries:

    * BasePerson                  --> BasePerson
    * BasePerson, TechnicalPerson --> TechnicalPerson
    * BasePerson, PilotPerson     --> PilotPerson
    
This automatic resolution is effected by ``neomodel.Database.cypher_objectaware_query`` which is 
invoked automatically where needed but it can also be invoked in exactly the same way as ``neomodel.
Database.cypher_query``, manually, wherever this functionality may be needed.

Doing so however, requires a bit of caution. As a consequence of the way the *node-class registry* is 
built up and used, if ``BasePerson``, ``TechnicalPerson``, ``PilotPerson`` were defined 
in separate files / modules and one of them was not loaded prior to a query to the database, then the 
*node-class registry* would be unaware of the labels that leads to that particular class and would raise 
``neomodel.exception.ModelDefinitionMismatch``.

If the exception is not handled, it produces an error message that returns the labels of the node that 
was retrieved from the database as well as the current *node-class registry*. These two pieces of 
information can be used to debug the model mismatch further.
    

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
