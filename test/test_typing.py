"""
Static-typing regression checks, verified by mypy in CI.

These functions are intentionally *not* run by pytest (they are underscore-
prefixed, and their bodies would hit the database). Their purpose is to make
mypy fail if the typed query/property API regresses. ``typing_extensions.
assert_type`` is a runtime no-op, so importing this module is side-effect free
apart from defining the model classes.

Run with::

    mypy test/test_typing.py
"""

from typing_extensions import assert_type

from neomodel import (
    AsyncStructuredNode,
    IntegerProperty,
    StringProperty,
    StructuredNode,
)


class TypingPerson(StructuredNode):
    name = StringProperty()
    age = IntegerProperty()


class AsyncTypingPerson(AsyncStructuredNode):
    name = StringProperty()
    age = IntegerProperty()


def _sync_query_types() -> None:
    # Gap 1: results are typed as the concrete class, not the base node type.
    assert_type(TypingPerson.nodes.get(name="x"), TypingPerson)
    assert_type(TypingPerson.nodes.all(), list[TypingPerson])
    assert_type(TypingPerson.nodes.get_or_none(name="x"), TypingPerson | None)
    assert_type(TypingPerson.nodes.first_or_none(), TypingPerson | None)
    # Filter chains preserve the element type.
    assert_type(TypingPerson.nodes.filter(age__gt=1).first(), TypingPerson)
    for person in TypingPerson.nodes:
        assert_type(person, TypingPerson)


async def _async_query_types() -> None:
    assert_type(await AsyncTypingPerson.nodes.get(name="x"), AsyncTypingPerson)
    assert_type(await AsyncTypingPerson.nodes.all(), list[AsyncTypingPerson])
    assert_type(
        await AsyncTypingPerson.nodes.get_or_none(name="x"),
        AsyncTypingPerson | None,
    )
    assert_type(
        await AsyncTypingPerson.nodes.filter(age__gt=1).first(), AsyncTypingPerson
    )
    async for person in AsyncTypingPerson.nodes:
        assert_type(person, AsyncTypingPerson)


def _property_types() -> None:
    # Gap 2: property access returns the Python value type, not the descriptor.
    person = TypingPerson(name="x", age=3)
    assert_type(person.name, str)
    assert_type(person.age, int)
