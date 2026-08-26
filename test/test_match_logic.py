"""
World-agnostic query/match logic tests.

These exercise pure match-layer building blocks — the ``Q`` filter object and
``Traversal`` definition validation — without touching the database or the
async/sync split. They used to live in ``test/async_/test_match_api.py`` and
were therefore transpiled and run twice behind a live Neo4j session, even
though the behaviour is identical in both worlds and needs no connection.
"""

from pytest import raises

from neomodel import IntegerProperty, Q, StringProperty, StructuredNode
from neomodel.sync_.match import Traversal
from neomodel.util import RelationshipDirection


class _Coffee(StructuredNode):
    name = StringProperty()
    price = IntegerProperty()


class _Supplier(StructuredNode):
    name = StringProperty()


def test_qbase():
    test_print_out = str(Q(price=5) | Q(price=10))
    test_repr = repr(Q(price=5) | Q(price=10))
    assert test_print_out == "(OR: ('price', 5), ('price', 10))"
    assert test_repr == "<Q: (OR: ('price', 5), ('price', 10))>"

    assert ("price", 5) in (Q(price=5) | Q(price=10))

    test_hash = set([Q(price_lt=30) | ~Q(price=5), Q(price_lt=30) | ~Q(price=5)])
    assert len(test_hash) == 1


def test_traversal_definition_keys_are_valid():
    muckefuck = _Coffee(name="Mukkefuck", price=1)

    with raises(ValueError):
        Traversal(
            muckefuck,
            "a_name",
            {
                "node_class": _Supplier,
                "direction": RelationshipDirection.INCOMING,
                "relationship_type": "KNOWS",
                "model": None,
            },
        )

    Traversal(
        muckefuck,
        "a_name",
        {
            "node_class": _Supplier,
            "direction": RelationshipDirection.INCOMING,
            "relation_type": "KNOWS",
            "model": None,
        },
    )
