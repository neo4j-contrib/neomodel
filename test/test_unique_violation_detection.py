"""
Unit tests for uniqueness-constraint violation detection.

Neo4j phrases a uniqueness violation differently depending on the server version
and on how the violating write happened. neomodel must recognise all of them so
they surface as ``UniqueProperty`` (not a generic ``ConstraintValidationFailed``).
In particular, batch ``create()`` uses ``UNWIND ... SET``, which on 4.x servers
reports "... share the property value ..." rather than "... already exists with
label ...". This is a pure-logic check, so it runs without a database and is not
transpiled.
"""

from neomodel.sync_.query import _is_unique_constraint_violation

# Inline CREATE on Neo4j 5.x / 2025.x.
MESSAGE_ALREADY_EXISTS = (
    "Node(0) already exists with label `Customer` and property `email` "
    "= 'jim@aol.com'"
)

# SET-based write (batch create's UNWIND ... SET, and 4.x servers generally).
MESSAGE_SHARE_VALUE = (
    "New data does not satisfy Constraint( id=8, "
    "name='constraint_unique_Customer_email', type='UNIQUENESS', "
    "schema=(:Customer {email}), ownedIndex=7 ): "
    'Both node 17 and node -1 share the property value ( String("jim@aol.com") )'
)

# A different kind of constraint (existence) must NOT be treated as a uniqueness
# violation - it should surface as a generic ConstraintValidationFailed.
MESSAGE_EXISTENCE = "Node(0) with label `Foo` must have the property `bar`"


def test_recognises_already_exists_message():
    assert _is_unique_constraint_violation(MESSAGE_ALREADY_EXISTS)


def test_recognises_share_property_value_message():
    assert _is_unique_constraint_violation(MESSAGE_SHARE_VALUE)


def test_does_not_match_non_uniqueness_constraint():
    assert not _is_unique_constraint_violation(MESSAGE_EXISTENCE)
