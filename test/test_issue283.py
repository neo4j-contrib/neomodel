"""
Provides a test case for issue 283 - "Inheritance breaks".

The issue is outlined here: https://github.com/neo4j-contrib/neomodel/issues/283
More information about the same issue at:
https://github.com/aanastasiou/neomodelInheritanceTest

The following example uses a recursive relationship for economy, but the 
idea remains the same: "Instantiate the correct type of node at the end of 
a relationship as specified by the model"
"""

import datetime
import os
import random

import pytest

import neomodel

try:
    basestring
except NameError:
    basestring = str


# Set up a very simple model for the tests
class PersonalRelationship(neomodel.StructuredRel):
    """
    A very simple relationship between two basePersons that simply records
    the date at which an acquaintance was established.
    This relationship should be carried over to anything that inherits from
    basePerson without any further effort.
    """

    on_date = neomodel.DateTimeProperty(default_now=True)


class BasePerson(neomodel.StructuredNode):
    """
    Base class for defining some basic sort of an actor.
    """

    name = neomodel.StringProperty(required=True, unique_index=True)
    friends_with = neomodel.RelationshipTo(
        "BasePerson", "FRIENDS_WITH", model=PersonalRelationship
    )


class TechnicalPerson(BasePerson):
    """
    A Technical person specialises BasePerson by adding their expertise.
    """

    expertise = neomodel.StringProperty(required=True)


class PilotPerson(BasePerson):
    """
    A pilot person specialises BasePerson by adding the type of airplane they
    can operate.
    """

    airplane = neomodel.StringProperty(required=True)


class BaseOtherPerson(neomodel.StructuredNode):
    """
    An obviously "wrong" class of actor to befriend BasePersons with.
    """

    car_color = neomodel.StringProperty(required=True)


class SomePerson(BaseOtherPerson):
    """
    Concrete class that simply derives from BaseOtherPerson.
    """

    pass


# Test cases
def test_automatic_result_resolution():
    """
    Node objects at the end of relationships are instantiated to their
    corresponding Python object.
    """

    # Create a few entities
    A = TechnicalPerson.get_or_create(
        {"name": "Grumpy", "expertise": "Grumpiness"}
    )[0]
    B = TechnicalPerson.get_or_create(
        {"name": "Happy", "expertise": "Unicorns"}
    )[0]
    C = TechnicalPerson.get_or_create(
        {"name": "Sleepy", "expertise": "Pillows"}
    )[0]

    # Add connections
    A.friends_with.connect(B)
    B.friends_with.connect(C)
    C.friends_with.connect(A)

    # If A is friends with B, then A's friends_with objects should be
    # TechnicalPerson (!NOT basePerson!)
    assert type(A.friends_with[0]) is TechnicalPerson

    A.delete()
    B.delete()
    C.delete()


def test_recursive_automatic_result_resolution():
    """
    Node objects are instantiated to native Python objects, both at the top
    level of returned results and in the case where they are returned within
    lists.
    """

    # Create a few entities
    A = TechnicalPerson.get_or_create(
        {"name": "Grumpier", "expertise": "Grumpiness"}
    )[0]
    B = TechnicalPerson.get_or_create(
        {"name": "Happier", "expertise": "Grumpiness"}
    )[0]
    C = TechnicalPerson.get_or_create(
        {"name": "Sleepier", "expertise": "Pillows"}
    )[0]
    D = TechnicalPerson.get_or_create(
        {"name": "Sneezier", "expertise": "Pillows"}
    )[0]

    # Retrieve mixed results, both at the top level and nested
    L, _ = neomodel.db.cypher_query(
        "MATCH (a:TechnicalPerson) "
        "WHERE a.expertise='Grumpiness' "
        "WITH collect(a) as Alpha "
        "MATCH (b:TechnicalPerson) "
        "WHERE b.expertise='Pillows' "
        "WITH Alpha, collect(b) as Beta "
        "RETURN [Alpha, [Beta, [Beta, ['Banana', "
        "Alpha]]]]",
        resolve_objects=True,
    )

    # Assert that a Node returned deep in a nested list structure is of the
    # correct type
    assert type(L[0][0][0][1][0][0][0][0]) is TechnicalPerson
    # Assert that primitive data types remain primitive data types
    assert issubclass(type(L[0][0][0][1][0][1][0][1][0][0]), basestring)

    A.delete()
    B.delete()
    C.delete()
    D.delete()


def test_validation_with_inheritance_from_db():
    """
    Objects descending from the specified class of a relationship's end-node are
    also perfectly valid to appear as end-node values too
    """

    # Create a few entities
    # Technical Persons
    A = TechnicalPerson.get_or_create(
        {"name": "Grumpy", "expertise": "Grumpiness"}
    )[0]
    B = TechnicalPerson.get_or_create(
        {"name": "Happy", "expertise": "Unicorns"}
    )[0]
    C = TechnicalPerson.get_or_create(
        {"name": "Sleepy", "expertise": "Pillows"}
    )[0]

    # Pilot Persons
    D = PilotPerson.get_or_create(
        {"name": "Porco Rosso", "airplane": "Savoia-Marchetti"}
    )[0]
    E = PilotPerson.get_or_create(
        {"name": "Jack Dalton", "airplane": "Beechcraft Model 18"}
    )[0]

    # TechnicalPersons can befriend PilotPersons and vice-versa and that's fine

    # TechnicalPersons befriend Technical Persons
    A.friends_with.connect(B)
    B.friends_with.connect(C)
    C.friends_with.connect(A)

    # Pilot Persons befriend Pilot Persons
    D.friends_with.connect(E)

    # Technical Persons befriend Pilot Persons
    A.friends_with.connect(D)
    E.friends_with.connect(C)

    # This now means that friends_with of a TechnicalPerson can
    # either be TechnicalPerson or Pilot Person (!NOT basePerson!)

    assert (type(A.friends_with[0]) is TechnicalPerson) or (
        type(A.friends_with[0]) is PilotPerson
    )
    assert (type(A.friends_with[1]) is TechnicalPerson) or (
        type(A.friends_with[1]) is PilotPerson
    )
    assert type(D.friends_with[0]) is PilotPerson

    A.delete()
    B.delete()
    C.delete()
    D.delete()
    E.delete()


def test_validation_enforcement_to_db():
    """
    If a connection between wrong types is attempted, raise an exception
    """

    # Create a few entities
    # Technical Persons
    A = TechnicalPerson.get_or_create(
        {"name": "Grumpy", "expertise": "Grumpiness"}
    )[0]
    B = TechnicalPerson.get_or_create(
        {"name": "Happy", "expertise": "Unicorns"}
    )[0]
    C = TechnicalPerson.get_or_create(
        {"name": "Sleepy", "expertise": "Pillows"}
    )[0]

    # Pilot Persons
    D = PilotPerson.get_or_create(
        {"name": "Porco Rosso", "airplane": "Savoia-Marchetti"}
    )[0]
    E = PilotPerson.get_or_create(
        {"name": "Jack Dalton", "airplane": "Beechcraft Model 18"}
    )[0]

    # Some Person
    F = SomePerson(car_color="Blue").save()

    # TechnicalPersons can befriend PilotPersons and vice-versa and that's fine
    A.friends_with.connect(B)
    B.friends_with.connect(C)
    C.friends_with.connect(A)
    D.friends_with.connect(E)
    A.friends_with.connect(D)
    E.friends_with.connect(C)

    # Trying to befriend a Technical Person with Some Person should raise an
    # exception
    with pytest.raises(ValueError):
        A.friends_with.connect(F)

    A.delete()
    B.delete()
    C.delete()
    D.delete()
    E.delete()
    F.delete()


def test_failed_result_resolution():
    """
    A Neo4j driver node FROM the database contains labels that are unaware to
    neomodel's Database class. This condition raises ClassDefinitionNotFound
    exception.
    """

    class RandomPerson(BasePerson):
        randomness = neomodel.FloatProperty(default=random.random)

    # A Technical Person...
    A = TechnicalPerson.get_or_create(
        {"name": "Grumpy", "expertise": "Grumpiness"}
    )[0]

    # A Random Person...
    B = RandomPerson.get_or_create({"name": "Mad Hatter"})[0]

    A.friends_with.connect(B)

    # Simulate the condition where the definition of class RandomPerson is not
    # known yet.
    del neomodel.db._NODE_CLASS_REGISTRY[
        frozenset(["RandomPerson", "BasePerson"])
    ]

    # Now try to instantiate a RandomPerson
    A = TechnicalPerson.get_or_create(
        {"name": "Grumpy", "expertise": "Grumpiness"}
    )[0]
    with pytest.raises(
        neomodel.exceptions.NodeClassNotDefined,
        match=r"Node with labels .* does not resolve to any of the known objects.*",
    ):
        for some_friend in A.friends_with:
            print(some_friend.name)

    A.delete()
    B.delete()


def test_node_label_mismatch():
    """
    A Neo4j driver node FROM the database contains a superset of the known
    labels.
    """

    class SuperTechnicalPerson(TechnicalPerson):
        superness = neomodel.FloatProperty(default=1.0)

    class UltraTechnicalPerson(SuperTechnicalPerson):
        ultraness = neomodel.FloatProperty(default=3.1415928)

    # Create a TechnicalPerson...
    A = TechnicalPerson.get_or_create(
        {"name": "Grumpy", "expertise": "Grumpiness"}
    )[0]
    # ...that is connected to an UltraTechnicalPerson
    F = UltraTechnicalPerson(
        name="Chewbaka", expertise="Aarrr wgh ggwaaah"
    ).save()
    A.friends_with.connect(F)

    # Forget about the UltraTechnicalPerson
    del neomodel.db._NODE_CLASS_REGISTRY[
        frozenset(
            [
                "UltraTechnicalPerson",
                "SuperTechnicalPerson",
                "TechnicalPerson",
                "BasePerson",
            ]
        )
    ]

    # Recall a TechnicalPerson and enumerate its friends.
    # One of them is UltraTechnicalPerson which would be returned as a valid
    # node to a friends_with query but is currently unknown to the node class registry.
    A = TechnicalPerson.get_or_create(
        {"name": "Grumpy", "expertise": "Grumpiness"}
    )[0]
    with pytest.raises(neomodel.exceptions.NodeClassNotDefined):
        for some_friend in A.friends_with:
            print(some_friend.name)


def test_attempted_class_redefinition():
    """
    A neomodel.StructuredNode class is attempted to be redefined.
    """

    def redefine_class_locally():
        # Since this test has already set up a class hierarchy in its global scope, we will try to redefine
        # SomePerson here.
        # The internal structure of the SomePerson entity does not matter at all here.
        class SomePerson(BaseOtherPerson):
            uid = neomodel.UniqueIdProperty()

    with pytest.raises(
        neomodel.exceptions.NodeClassAlreadyDefined,
        match=r"Class .* with labels .* already defined:.*",
    ):
        redefine_class_locally()


def test_relationship_result_resolution():
    """
    A query returning a "Relationship" object can now instantiate it to a data model class
    """
    # Test specific data
    A = PilotPerson(
        name="Zantford Granville", airplane="Gee Bee Model R"
    ).save()
    B = PilotPerson(name="Thomas Granville", airplane="Gee Bee Model R").save()
    C = PilotPerson(name="Robert Granville", airplane="Gee Bee Model R").save()
    D = PilotPerson(name="Mark Granville", airplane="Gee Bee Model R").save()
    E = PilotPerson(name="Edward Granville", airplane="Gee Bee Model R").save()

    A.friends_with.connect(B)
    B.friends_with.connect(C)
    C.friends_with.connect(D)
    D.friends_with.connect(E)

    query_data = neomodel.db.cypher_query(
        "MATCH (a:PilotPerson)-[r:FRIENDS_WITH]->(b:PilotPerson) "
        "WHERE a.airplane='Gee Bee Model R' and b.airplane='Gee Bee Model R' "
        "RETURN DISTINCT r",
        resolve_objects=True,
    )

    # The relationship here should be properly instantiated to a `PersonalRelationship` object.
    assert isinstance(query_data[0][0][0], PersonalRelationship)


def test_properly_inherited_relationship():
    """
    A relationship class extends an existing relationship model that must extended the same previously associated
    relationship label.
    """

    # Extends an existing relationship by adding the "relationship_strength" attribute.
    # `ExtendedPersonalRelationship` will now substitute `PersonalRelationship` EVERYWHERE in the system.
    class ExtendedPersonalRelationship(PersonalRelationship):
        relationship_strength = neomodel.FloatProperty(default=random.random)

    # Extends SomePerson, establishes "enriched" relationships with any BaseOtherPerson
    class ExtendedSomePerson(SomePerson):
        friends_with = neomodel.RelationshipTo(
            "BaseOtherPerson",
            "FRIENDS_WITH",
            model=ExtendedPersonalRelationship,
        )

    # Test specific data
    A = ExtendedSomePerson(name="Michael Knight", car_color="Black").save()
    B = ExtendedSomePerson(name="Luke Duke", car_color="Orange").save()
    C = ExtendedSomePerson(name="Michael Schumacher", car_color="Red").save()

    A.friends_with.connect(B)
    A.friends_with.connect(C)

    query_data = neomodel.db.cypher_query(
        "MATCH (:ExtendedSomePerson)-[r:FRIENDS_WITH]->(:ExtendedSomePerson) "
        "RETURN DISTINCT r",
        resolve_objects=True,
    )

    assert isinstance(query_data[0][0][0], ExtendedPersonalRelationship)


def test_improperly_inherited_relationship():
    """
    Attempting to re-define an existing relationship with a completely unrelated class.
    :return:
    """

    class NewRelationship(neomodel.StructuredRel):
        profile_match_factor = neomodel.FloatProperty()

    with pytest.raises(
        neomodel.RelationshipClassRedefined,
        match=r"Relationship of type .* redefined as .*",
    ):

        class NewSomePerson(SomePerson):
            friends_with = neomodel.RelationshipTo(
                "BaseOtherPerson", "FRIENDS_WITH", model=NewRelationship
            )


def test_resolve_inexistent_relationship():
    """
    Attempting to resolve an inexistent relationship should raise an exception
    :return:
    """

    # Forget about the FRIENDS_WITH Relationship.
    del neomodel.db._NODE_CLASS_REGISTRY[frozenset(["FRIENDS_WITH"])]

    with pytest.raises(
        neomodel.RelationshipClassNotDefined,
        match=r"Relationship of type .* does not resolve to any of the known objects.*",
    ):
        query_data = neomodel.db.cypher_query(
            "MATCH (:ExtendedSomePerson)-[r:FRIENDS_WITH]->(:ExtendedSomePerson) "
            "RETURN DISTINCT r",
            resolve_objects=True,
        )
