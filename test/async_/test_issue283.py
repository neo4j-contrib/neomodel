"""
Provides a test case for issue 283 - "Inheritance breaks".

The issue is outlined here: https://github.com/neo4j-contrib/neomodel/issues/283
More information about the same issue at:
https://github.com/aanastasiou/neomodelInheritanceTest

The following example uses a recursive relationship for economy, but the
idea remains the same: "Instantiate the correct type of node at the end of
a relationship as specified by the model"
"""

import random
from test._async_compat import mark_async_test

import pytest

from neomodel import (
    AsyncRelationshipTo,
    AsyncStructuredNode,
    AsyncStructuredRel,
    DateTimeProperty,
    FloatProperty,
    RelationshipClassNotDefined,
    RelationshipClassRedefined,
    StringProperty,
    adb,
)
from neomodel.exceptions import NodeClassAlreadyDefined, NodeClassNotDefined

try:
    basestring
except NameError:
    basestring = str


# Set up a very simple model for the tests
class PersonalRelationship(AsyncStructuredRel):
    """
    A very simple relationship between two basePersons that simply records
    the date at which an acquaintance was established.
    This relationship should be carried over to anything that inherits from
    basePerson without any further effort.
    """

    on_date = DateTimeProperty(default_now=True)


class BasePerson(AsyncStructuredNode):
    """
    Base class for defining some basic sort of an actor.
    """

    name = StringProperty(required=True, unique_index=True)
    friends_with = AsyncRelationshipTo(
        "BasePerson", "FRIENDS_WITH", model=PersonalRelationship
    )


class TechnicalPerson(BasePerson):
    """
    A Technical person specialises BasePerson by adding their expertise.
    """

    expertise = StringProperty(required=True)


class PilotPerson(BasePerson):
    """
    A pilot person specialises BasePerson by adding the type of airplane they
    can operate.
    """

    airplane = StringProperty(required=True)


class BaseOtherPerson(AsyncStructuredNode):
    """
    An obviously "wrong" class of actor to befriend BasePersons with.
    """

    car_color = StringProperty(required=True)


class SomePerson(BaseOtherPerson):
    """
    Concrete class that simply derives from BaseOtherPerson.
    """

    pass


# Test cases
@mark_async_test
async def test_automatic_result_resolution():
    """
    Node objects at the end of relationships are instantiated to their
    corresponding Python object.
    """

    # Create a few entities
    A = (
        await TechnicalPerson.get_or_create(
            {"name": "Grumpy", "expertise": "Grumpiness"}
        )
    )[0]
    B = (
        await TechnicalPerson.get_or_create({"name": "Happy", "expertise": "Unicorns"})
    )[0]
    C = (
        await TechnicalPerson.get_or_create({"name": "Sleepy", "expertise": "Pillows"})
    )[0]

    # Add connections
    await A.friends_with.connect(B)
    await B.friends_with.connect(C)
    await C.friends_with.connect(A)

    test = await A.friends_with

    # If A is friends with B, then A's friends_with objects should be
    # TechnicalPerson (!NOT basePerson!)
    assert type((await A.friends_with)[0]) is TechnicalPerson


@mark_async_test
async def test_validation_with_inheritance_from_db():
    """
    Objects descending from the specified class of a relationship's end-node are
    also perfectly valid to appear as end-node values too
    """

    # Create a few entities
    # Technical Persons
    A = (
        await TechnicalPerson.get_or_create(
            {"name": "Grumpy", "expertise": "Grumpiness"}
        )
    )[0]
    B = (
        await TechnicalPerson.get_or_create({"name": "Happy", "expertise": "Unicorns"})
    )[0]
    C = (
        await TechnicalPerson.get_or_create({"name": "Sleepy", "expertise": "Pillows"})
    )[0]

    # Pilot Persons
    D = (
        await PilotPerson.get_or_create(
            {"name": "Porco Rosso", "airplane": "Savoia-Marchetti"}
        )
    )[0]
    E = (
        await PilotPerson.get_or_create(
            {"name": "Jack Dalton", "airplane": "Beechcraft Model 18"}
        )
    )[0]

    # TechnicalPersons can befriend PilotPersons and vice-versa and that's fine

    # TechnicalPersons befriend Technical Persons
    await A.friends_with.connect(B)
    await B.friends_with.connect(C)
    await C.friends_with.connect(A)

    # Pilot Persons befriend Pilot Persons
    await D.friends_with.connect(E)

    # Technical Persons befriend Pilot Persons
    await A.friends_with.connect(D)
    await E.friends_with.connect(C)

    # This now means that friends_with of a TechnicalPerson can
    # either be TechnicalPerson or Pilot Person (!NOT basePerson!)

    assert (type((await A.friends_with)[0]) is TechnicalPerson) or (
        type((await A.friends_with)[0]) is PilotPerson
    )
    assert (type((await A.friends_with)[1]) is TechnicalPerson) or (
        type((await A.friends_with)[1]) is PilotPerson
    )
    assert type((await D.friends_with)[0]) is PilotPerson


@mark_async_test
async def test_validation_enforcement_to_db():
    """
    If a connection between wrong types is attempted, raise an exception
    """

    # Create a few entities
    # Technical Persons
    A = (
        await TechnicalPerson.get_or_create(
            {"name": "Grumpy", "expertise": "Grumpiness"}
        )
    )[0]
    B = (
        await TechnicalPerson.get_or_create({"name": "Happy", "expertise": "Unicorns"})
    )[0]
    C = (
        await TechnicalPerson.get_or_create({"name": "Sleepy", "expertise": "Pillows"})
    )[0]

    # Pilot Persons
    D = (
        await PilotPerson.get_or_create(
            {"name": "Porco Rosso", "airplane": "Savoia-Marchetti"}
        )
    )[0]
    E = (
        await PilotPerson.get_or_create(
            {"name": "Jack Dalton", "airplane": "Beechcraft Model 18"}
        )
    )[0]

    # Some Person
    F = await SomePerson(car_color="Blue").save()

    # TechnicalPersons can befriend PilotPersons and vice-versa and that's fine
    await A.friends_with.connect(B)
    await B.friends_with.connect(C)
    await C.friends_with.connect(A)
    await D.friends_with.connect(E)
    await A.friends_with.connect(D)
    await E.friends_with.connect(C)

    # Trying to befriend a Technical Person with Some Person should raise an
    # exception
    with pytest.raises(ValueError):
        await A.friends_with.connect(F)


@mark_async_test
async def test_failed_result_resolution():
    """
    A Neo4j driver node FROM the database contains labels that no known neomodel
    class maps to. Resolving it raises NodeClassNotDefined.
    """

    # A Technical Person...
    A = (
        await TechnicalPerson.get_or_create(
            {"name": "Grumpy", "expertise": "Grumpiness"}
        )
    )[0]

    # ...befriends a node that carries the BasePerson label (so it comes back
    # through the FRIENDS_WITH traversal) plus a label no live class is mapped
    # to. This is the "class not imported / unknown to neomodel" condition,
    # which no amount of registry poking is needed to reproduce now that classes
    # are discovered from the live hierarchy.
    await adb.cypher_query(
        "MATCH (a:BasePerson {name: $name}) "
        "CREATE (a)-[:FRIENDS_WITH]->(:BasePerson:UnknownSpecialisation {name: 'Mystery'})",
        {"name": "Grumpy"},
    )

    with pytest.raises(
        NodeClassNotDefined,
        match=r"Node with labels .* does not resolve to any of the known objects.*",
    ):
        friends = await A.friends_with.all()
        for some_friend in friends:
            print(some_friend.name)


@mark_async_test
async def test_node_label_mismatch():
    """
    A Neo4j driver node FROM the database contains a superset of a known class's
    labels (extra labels that are not declared optional), so it resolves to no
    class and raises NodeClassNotDefined.
    """

    # Create a TechnicalPerson...
    A = (
        await TechnicalPerson.get_or_create(
            {"name": "Grumpy", "expertise": "Grumpiness"}
        )
    )[0]
    # ...connected to a node that carries every label a TechnicalPerson has PLUS
    # an extra, non-optional label. No live class maps to that exact superset.
    await adb.cypher_query(
        "MATCH (a:BasePerson {name: $name}) "
        "CREATE (a)-[:FRIENDS_WITH]->"
        "(:BasePerson:TechnicalPerson:PhantomSpecialisation {name: 'Ghost', expertise: 'Haunting'})",
        {"name": "Grumpy"},
    )

    with pytest.raises(NodeClassNotDefined):
        friends = await A.friends_with.all()
        for some_friend in friends:
            print(some_friend.name)


@mark_async_test
async def test_attempted_class_redefinition():
    """
    Two *distinct* live classes claiming the same labels are no longer rejected
    at definition time; the clash is reported when a matching node is resolved.
    (A same-name reload, by contrast, is allowed - see
    test/async_/test_registry.py::test_class_redefinition_is_allowed.)
    """

    class FirstColliding(AsyncStructuredNode):
        __label__ = "CollidingLabel"
        name = StringProperty()

    class SecondColliding(AsyncStructuredNode):
        __label__ = "CollidingLabel"
        title = StringProperty()

    await adb.cypher_query("CREATE (:CollidingLabel {name: 'x'})")
    with pytest.raises(
        NodeClassAlreadyDefined,
        match=r"Class .* with labels .* already defined:.*",
    ):
        await adb.cypher_query(
            "MATCH (n:CollidingLabel) RETURN n", resolve_objects=True
        )


@mark_async_test
async def test_relationship_result_resolution():
    """
    A query returning a "Relationship" object can now instantiate it to a data model class
    """
    # Test specific data
    A = await PilotPerson(name="Zantford Granville", airplane="Gee Bee Model R").save()
    B = await PilotPerson(name="Thomas Granville", airplane="Gee Bee Model R").save()
    C = await PilotPerson(name="Robert Granville", airplane="Gee Bee Model R").save()
    D = await PilotPerson(name="Mark Granville", airplane="Gee Bee Model R").save()
    E = await PilotPerson(name="Edward Granville", airplane="Gee Bee Model R").save()

    await A.friends_with.connect(B)
    await B.friends_with.connect(C)
    await C.friends_with.connect(D)
    await D.friends_with.connect(E)

    query_data = await adb.cypher_query(
        "MATCH (a:PilotPerson)-[r:FRIENDS_WITH]->(b:PilotPerson) "
        "WHERE a.airplane='Gee Bee Model R' and b.airplane='Gee Bee Model R' "
        "RETURN DISTINCT r",
        resolve_objects=True,
    )

    # The relationship here should be properly instantiated to a `PersonalRelationship` object.
    assert isinstance(query_data[0][0][0], PersonalRelationship)


@mark_async_test
async def test_properly_inherited_relationship():
    """
    A relationship class extends an existing relationship model that must extended the same previously associated
    relationship label.
    """

    # Extends an existing relationship by adding the "relationship_strength" attribute.
    # `ExtendedPersonalRelationship` will now substitute `PersonalRelationship` EVERYWHERE in the system.
    class ExtendedPersonalRelationship(PersonalRelationship):
        relationship_strength = FloatProperty(default=random.random)

    # Extends SomePerson, establishes "enriched" relationships with any BaseOtherPerson
    class ExtendedSomePerson(SomePerson):
        friends_with = AsyncRelationshipTo(
            "BaseOtherPerson",
            "FRIENDS_WITH",
            model=ExtendedPersonalRelationship,
        )

    # Test specific data
    A = await ExtendedSomePerson(name="Michael Knight", car_color="Black").save()
    B = await ExtendedSomePerson(name="Luke Duke", car_color="Orange").save()
    C = await ExtendedSomePerson(name="Michael Schumacher", car_color="Red").save()

    await A.friends_with.connect(B)
    await A.friends_with.connect(C)

    query_data = await adb.cypher_query(
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

    class NewRelationship(AsyncStructuredRel):
        profile_match_factor = FloatProperty()

    with pytest.raises(
        RelationshipClassRedefined,
        match=r"Relationship of type .* redefined as .*",
    ):

        class NewSomePerson(SomePerson):
            friends_with = AsyncRelationshipTo(
                "BaseOtherPerson", "FRIENDS_WITH", model=NewRelationship
            )


@mark_async_test
async def test_resolve_inexistent_relationship():
    """
    Attempting to resolve an inexistent relationship should raise an exception
    :return:
    """
    A = await TechnicalPerson(name="Michael Knight", expertise="Cars").save()
    B = await TechnicalPerson(name="Luke Duke", expertise="Lasers").save()

    await A.friends_with.connect(B)

    # Forget about the FRIENDS_WITH Relationship.
    del adb._NODE_CLASS_REGISTRY[frozenset(["FRIENDS_WITH"])]

    with pytest.raises(
        RelationshipClassNotDefined,
        match=r"Relationship of type .* does not resolve to any of the known objects.*",
    ):
        query_data = await adb.cypher_query(
            "MATCH (:TechnicalPerson)-[r:FRIENDS_WITH]->(:TechnicalPerson) "
            "RETURN DISTINCT r",
            resolve_objects=True,
        )
