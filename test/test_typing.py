"""
Type checking tests for neomodel type stubs.

These tests verify that the type stubs correctly infer types for properties
and catch type errors. They are meant to be checked by mypy, not executed at runtime.

Run with: mypy test/test_typing.py
"""

from datetime import date, datetime
from typing import Any

from neomodel import (
    ArrayProperty,
    BooleanProperty,
    DateProperty,
    DateTimeProperty,
    FloatProperty,
    IntegerProperty,
    JSONProperty,
    RelationshipFrom,
    RelationshipTo,
    StringProperty,
    StructuredNode,
    UniqueIdProperty,
    ZeroOrMore,
)


class Company(StructuredNode):
    """Test company node."""

    name = StringProperty(required=True)
    founded_year = IntegerProperty()


class Person(StructuredNode):
    """Test person node with various property types."""

    uid = UniqueIdProperty()
    name = StringProperty(required=True)
    age = IntegerProperty()
    email = StringProperty()
    height = FloatProperty()
    active = BooleanProperty()
    birth_date = DateProperty()
    created_at = DateTimeProperty()
    tags = ArrayProperty(StringProperty())
    metadata = JSONProperty()

    # Relationships
    company = RelationshipTo("Company", "WORKS_FOR", cardinality=ZeroOrMore)
    friends = RelationshipTo("Person", "FRIEND_OF", cardinality=ZeroOrMore)
    managed_by = RelationshipFrom("Person", "MANAGES", cardinality=ZeroOrMore)


# Test 1: Property type inference
def test_property_types() -> None:
    """Verify that property access returns correct types."""
    person = Person()

    # These should all type-check correctly
    name_str: str = person.name
    age_int: int = person.age
    height_float: float = person.height
    active_bool: bool = person.active
    birth_date_val: date = person.birth_date
    created_at_val: datetime = person.created_at
    tags_list: list = person.tags
    metadata_any: Any = person.metadata
    uid_str: str = person.uid


# Test 2: Property assignments
def test_property_assignments() -> None:
    """Verify that property assignments accept correct types."""
    person = Person()

    # These should all type-check correctly
    person.name = "Alice"
    person.age = 30
    person.height = 1.75
    person.active = True
    person.birth_date = date(1990, 1, 1)
    person.created_at = datetime(2024, 1, 1, 12, 0, 0)
    person.tags = ["developer", "python"]
    person.metadata = {"key": "value"}


# Test 3: Class-level access returns property descriptor
def test_class_level_access() -> None:
    """Verify that class-level access returns the property descriptor."""
    # These should return the property classes themselves
    name_prop: StringProperty = Person.name
    age_prop: IntegerProperty = Person.age
    height_prop: FloatProperty = Person.height
    active_prop: BooleanProperty = Person.active


# Test 4: Type errors should be caught
def test_type_errors() -> None:
    """These should produce type errors when checked with mypy."""
    person = Person()

    # Type error: str incompatible with int
    wrong_type_1: int = person.name  # type: ignore[assignment]

    # Type error: int incompatible with str
    wrong_type_2: str = person.age  # type: ignore[assignment]

    # Type error: assigning wrong type to property
    person.age = "thirty"  # type: ignore[assignment]

    # Type error: assigning wrong type to property
    person.active = "yes"  # type: ignore[assignment]


# Test 5: String operations on string properties
def test_string_operations() -> None:
    """Verify that string methods work on string properties."""
    person = Person()
    person.name = "alice"

    # Should type-check: name is str, has .upper() method
    uppercase: str = person.name.upper()
    lowercase: str = person.name.lower()
    capitalized: str = person.name.capitalize()

    assert uppercase  # Satisfy linter
    assert lowercase
    assert capitalized


# Test 6: Numeric operations
def test_numeric_operations() -> None:
    """Verify that numeric operations work on numeric properties."""
    person = Person()
    person.age = 30
    person.height = 1.75

    # Should type-check: age is int, height is float
    next_age: int = person.age + 1
    double_height: float = person.height * 2.0

    assert next_age
    assert double_height


# Test 7: NodeSet operations
def test_nodeset_operations() -> None:
    """Verify NodeSet operations type-check correctly."""
    # Should type-check
    all_people: list = Person.nodes.all()
    adults = Person.nodes.filter(age__gte=18)
    first_person = Person.nodes.first()

    assert all_people or adults or first_person


# Test 8: Relationship operations - commented out as these need RelationshipManager stubs
# def test_relationship_operations() -> None:
#     """Verify relationship operations type-check correctly."""
#     person = Person()
#     company = Company()
#
#     # Should type-check
#     person.company.connect(company)
#     is_connected: bool = person.company.is_connected(company)
