import warnings
from test._async_compat import mark_sync_test

import pytest

from neomodel import (
    MutualExclusionViolation,
    One,
    RelationshipTo,
    StringProperty,
    StructuredNode,
    ZeroOrOne,
)


class JealousCat(StructuredNode):
    name = StringProperty(required=True)


class JealousDog(StructuredNode):
    name = StringProperty(required=True)


class Fish(StructuredNode):
    name = StringProperty(required=True)


class PetOwner(StructuredNode):
    name = StringProperty(required=True)

    # Mutually exclusive relationships in group "pet", each with its OWN
    # cardinality - the two concerns are orthogonal.
    cat = RelationshipTo(
        "JealousCat", "HAS_PET", cardinality=ZeroOrOne, exclusion_group="pet"
    )
    dog = RelationshipTo(
        "JealousDog", "HAS_PET", cardinality=One, exclusion_group="pet"
    )
    fish = RelationshipTo(
        "Fish", "HAS_PET", cardinality=ZeroOrOne, exclusion_group="pet"
    )


@mark_sync_test
def test_exclusion_blocks_sibling_connect():
    owner = PetOwner(name="Alice").save()
    cat = JealousCat(name="Tom").save()
    dog = JealousDog(name="Spike").save()

    owner.cat.connect(cat)

    # dog and fish share the "pet" group with cat, which is already connected
    with pytest.raises(MutualExclusionViolation, match=r"mutual exclusion group 'pet'"):
        owner.dog.connect(dog)
    fish = Fish(name="Nemo").save()
    with pytest.raises(MutualExclusionViolation, match=r"mutual exclusion group 'pet'"):
        owner.fish.connect(fish)


@mark_sync_test
def test_exclusion_is_orthogonal_to_cardinality():
    """The cardinality of the chosen relationship still applies."""
    owner = PetOwner(name="Bob").save()
    cat1 = JealousCat(name="Felix").save()
    cat2 = JealousCat(name="Garfield").save()

    owner.cat.connect(cat1)

    # cat is ZeroOrOne: a second cat violates its own cardinality, not exclusion
    from neomodel import AttemptedCardinalityViolation

    with pytest.raises(AttemptedCardinalityViolation):
        owner.cat.connect(cat2)


@mark_sync_test
def test_exclusion_allows_reconnect_within_same_relationship():
    """Swapping the target of the same relationship is fine - no new group member."""
    owner = PetOwner(name="Carol").save()
    cat1 = JealousCat(name="Whiskers").save()
    cat2 = JealousCat(name="Mittens").save()

    owner.cat.connect(cat1)
    owner.cat.reconnect(cat1, cat2)

    assert (owner.cat.single()).name == "Mittens"


@mark_sync_test
def test_exclusion_applies_on_replace():
    owner = PetOwner(name="Dave").save()
    cat = JealousCat(name="Sylvester").save()

    owner.cat.connect(cat)

    # replace() connects a new edge in the group -> still blocked while cat holds
    # one. fish is ZeroOrOne, so its disconnect_all()/replace() is permitted.
    fish = Fish(name="Nemo").save()
    with pytest.raises(MutualExclusionViolation, match=r"mutual exclusion group 'pet'"):
        owner.fish.replace(fish)


@mark_sync_test
def test_exclusion_allows_connect_after_disconnect():
    owner = PetOwner(name="Erin").save()
    cat = JealousCat(name="Tom").save()
    dog = JealousDog(name="Spike").save()

    owner.cat.connect(cat)
    # disconnect the cat, then the dog becomes allowed
    owner.cat.disconnect(cat)
    owner.dog.connect(dog)

    assert (owner.dog.single()).name == "Spike"


def test_single_member_exclusion_group_warns():
    # The warning is emitted by the node metaclass, at class creation time.
    solo_rel = RelationshipTo("JealousCat", "HAS_SOLO", exclusion_group="lonely")
    with pytest.warns(
        UserWarning, match=r"exclusion group 'lonely' on .* has a single member"
    ):

        class OneMemberGroup(StructuredNode):
            solo = solo_rel


def test_valid_exclusion_group_does_not_warn():
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # any warning becomes an error

        class TwoMemberGroup(StructuredNode):
            name = StringProperty(required=True)
            a = RelationshipTo("JealousCat", "HAS_A", exclusion_group="paired")
            b = RelationshipTo("JealousDog", "HAS_B", exclusion_group="paired")
