import warnings
from test._async_compat import mark_async_test

from pytest import raises, warns

from neomodel import (
    AsyncOne,
    AsyncRelationshipTo,
    AsyncStructuredNode,
    AsyncZeroOrOne,
    MutualExclusionViolation,
    StringProperty,
)


class JealousCat(AsyncStructuredNode):
    name = StringProperty(required=True)


class JealousDog(AsyncStructuredNode):
    name = StringProperty(required=True)


class Fish(AsyncStructuredNode):
    name = StringProperty(required=True)


class PetOwner(AsyncStructuredNode):
    name = StringProperty(required=True)

    # Mutually exclusive relationships in group "pet", each with its OWN
    # cardinality - the two concerns are orthogonal.
    cat = AsyncRelationshipTo(
        "JealousCat", "HAS_PET", cardinality=AsyncZeroOrOne, exclusion_group="pet"
    )
    dog = AsyncRelationshipTo(
        "JealousDog", "HAS_PET", cardinality=AsyncOne, exclusion_group="pet"
    )
    fish = AsyncRelationshipTo(
        "Fish", "HAS_PET", cardinality=AsyncZeroOrOne, exclusion_group="pet"
    )


@mark_async_test
async def test_exclusion_blocks_sibling_connect():
    owner = await PetOwner(name="Alice").save()
    cat = await JealousCat(name="Tom").save()
    dog = await JealousDog(name="Spike").save()

    await owner.cat.connect(cat)

    # dog and fish share the "pet" group with cat, which is already connected
    with raises(MutualExclusionViolation, match=r"mutual exclusion group 'pet'"):
        await owner.dog.connect(dog)
    with raises(MutualExclusionViolation, match=r"mutual exclusion group 'pet'"):
        await owner.fish.connect(await Fish(name="Nemo").save())


@mark_async_test
async def test_exclusion_is_orthogonal_to_cardinality():
    """The cardinality of the chosen relationship still applies."""
    owner = await PetOwner(name="Bob").save()
    cat1 = await JealousCat(name="Felix").save()
    cat2 = await JealousCat(name="Garfield").save()

    await owner.cat.connect(cat1)

    # cat is ZeroOrOne: a second cat violates its own cardinality, not exclusion
    from neomodel import AttemptedCardinalityViolation

    with raises(AttemptedCardinalityViolation):
        await owner.cat.connect(cat2)


@mark_async_test
async def test_exclusion_allows_reconnect_within_same_relationship():
    """Swapping the target of the same relationship is fine - no new group member."""
    owner = await PetOwner(name="Carol").save()
    cat1 = await JealousCat(name="Whiskers").save()
    cat2 = await JealousCat(name="Mittens").save()

    await owner.cat.connect(cat1)
    await owner.cat.reconnect(cat1, cat2)

    assert (await owner.cat.single()).name == "Mittens"


@mark_async_test
async def test_exclusion_applies_on_replace():
    owner = await PetOwner(name="Dave").save()
    cat = await JealousCat(name="Sylvester").save()

    await owner.cat.connect(cat)

    # replace() connects a new edge in the group -> still blocked while cat holds
    # one. fish is ZeroOrOne, so its disconnect_all()/replace() is permitted.
    with raises(MutualExclusionViolation, match=r"mutual exclusion group 'pet'"):
        await owner.fish.replace(await Fish(name="Nemo").save())


@mark_async_test
async def test_exclusion_allows_connect_after_disconnect():
    owner = await PetOwner(name="Erin").save()
    cat = await JealousCat(name="Tom").save()
    dog = await JealousDog(name="Spike").save()

    await owner.cat.connect(cat)
    # disconnect the cat, then the dog becomes allowed
    await owner.cat.disconnect(cat)
    await owner.dog.connect(dog)

    assert (await owner.dog.single()).name == "Spike"


def test_single_member_exclusion_group_warns():
    with warns(
        UserWarning, match=r"exclusion group 'lonely' on .* has a single member"
    ):

        class OneMemberGroup(AsyncStructuredNode):
            name = StringProperty(required=True)
            solo = AsyncRelationshipTo(
                "JealousCat", "HAS_SOLO", exclusion_group="lonely"
            )


def test_valid_exclusion_group_does_not_warn():
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # any warning becomes an error

        class TwoMemberGroup(AsyncStructuredNode):
            name = StringProperty(required=True)
            a = AsyncRelationshipTo("JealousCat", "HAS_A", exclusion_group="paired")
            b = AsyncRelationshipTo("JealousDog", "HAS_B", exclusion_group="paired")
