"""
Provides a test case for issue 600 - "Pull request #592 cause an error in case of relationship inharitance".

The issue is outlined here: https://github.com/neo4j-contrib/neomodel/issues/600
"""

from test._async_compat import mark_async_test

from neomodel import AsyncRelationship, AsyncStructuredNode, AsyncStructuredRel

try:
    basestring
except NameError:
    basestring = str


class Class1(AsyncStructuredRel):
    pass


class SubClass1(Class1):
    pass


class SubClass2(Class1):
    pass


class RelationshipDefinerSecondSibling(AsyncStructuredNode):
    rel_1 = AsyncRelationship(
        "RelationshipDefinerSecondSibling", "SOME_REL_LABEL", model=Class1
    )
    rel_2 = AsyncRelationship(
        "RelationshipDefinerSecondSibling", "SOME_REL_LABEL", model=SubClass1
    )
    rel_3 = AsyncRelationship(
        "RelationshipDefinerSecondSibling", "SOME_REL_LABEL", model=SubClass2
    )


class RelationshipDefinerParentLast(AsyncStructuredNode):
    rel_2 = AsyncRelationship(
        "RelationshipDefinerParentLast", "SOME_REL_LABEL", model=SubClass1
    )
    rel_3 = AsyncRelationship(
        "RelationshipDefinerParentLast", "SOME_REL_LABEL", model=SubClass2
    )
    rel_1 = AsyncRelationship(
        "RelationshipDefinerParentLast", "SOME_REL_LABEL", model=Class1
    )


# Test cases
@mark_async_test
async def test_relationship_definer_second_sibling():
    # Create a few entities
    A = (await RelationshipDefinerSecondSibling.get_or_create({}))[0]
    B = (await RelationshipDefinerSecondSibling.get_or_create({}))[0]
    C = (await RelationshipDefinerSecondSibling.get_or_create({}))[0]

    # Add connections
    await A.rel_1.connect(B)
    await B.rel_2.connect(C)
    await C.rel_3.connect(A)

    # Clean up
    await A.delete()
    await B.delete()
    await C.delete()


@mark_async_test
async def test_relationship_definer_parent_last():
    # Create a few entities
    A = (await RelationshipDefinerParentLast.get_or_create({}))[0]
    B = (await RelationshipDefinerParentLast.get_or_create({}))[0]
    C = (await RelationshipDefinerParentLast.get_or_create({}))[0]

    # Add connections
    await A.rel_1.connect(B)
    await B.rel_2.connect(C)
    await C.rel_3.connect(A)

    # Clean up
    await A.delete()
    await B.delete()
    await C.delete()
