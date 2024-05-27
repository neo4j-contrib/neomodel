"""
Provides a test case for issue 600 - "Pull request #592 cause an error in case of relationship inharitance".

The issue is outlined here: https://github.com/neo4j-contrib/neomodel/issues/600
"""

from test._async_compat import mark_sync_test

from neomodel import Relationship, StructuredNode, StructuredRel

try:
    basestring
except NameError:
    basestring = str


class Class1(StructuredRel):
    pass


class SubClass1(Class1):
    pass


class SubClass2(Class1):
    pass


class RelationshipDefinerSecondSibling(StructuredNode):
    rel_1 = Relationship(
        "RelationshipDefinerSecondSibling", "SOME_REL_LABEL", model=Class1
    )
    rel_2 = Relationship(
        "RelationshipDefinerSecondSibling", "SOME_REL_LABEL", model=SubClass1
    )
    rel_3 = Relationship(
        "RelationshipDefinerSecondSibling", "SOME_REL_LABEL", model=SubClass2
    )


class RelationshipDefinerParentLast(StructuredNode):
    rel_2 = Relationship(
        "RelationshipDefinerParentLast", "SOME_REL_LABEL", model=SubClass1
    )
    rel_3 = Relationship(
        "RelationshipDefinerParentLast", "SOME_REL_LABEL", model=SubClass2
    )
    rel_1 = Relationship(
        "RelationshipDefinerParentLast", "SOME_REL_LABEL", model=Class1
    )


# Test cases
@mark_sync_test
def test_relationship_definer_second_sibling():
    # Create a few entities
    A = (RelationshipDefinerSecondSibling.get_or_create({}))[0]
    B = (RelationshipDefinerSecondSibling.get_or_create({}))[0]
    C = (RelationshipDefinerSecondSibling.get_or_create({}))[0]

    # Add connections
    A.rel_1.connect(B)
    B.rel_2.connect(C)
    C.rel_3.connect(A)

    # Clean up
    A.delete()
    B.delete()
    C.delete()


@mark_sync_test
def test_relationship_definer_parent_last():
    # Create a few entities
    A = (RelationshipDefinerParentLast.get_or_create({}))[0]
    B = (RelationshipDefinerParentLast.get_or_create({}))[0]
    C = (RelationshipDefinerParentLast.get_or_create({}))[0]

    # Add connections
    A.rel_1.connect(B)
    B.rel_2.connect(C)
    C.rel_3.connect(A)

    # Clean up
    A.delete()
    B.delete()
    C.delete()
