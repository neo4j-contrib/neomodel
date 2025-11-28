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
    NodeSet,
    RelationshipFrom,
    RelationshipTo,
    StringProperty,
    StructuredNode,
    UniqueIdProperty,
    ZeroOrMore,
)


class MypyCompany(StructuredNode):
    """Test company node."""

    name = StringProperty(required=True)
    founded_year = IntegerProperty()


class MypyPerson(StructuredNode):
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
    company: RelationshipTo = RelationshipTo(
        "MypyCompany", "WORKS_FOR", cardinality=ZeroOrMore
    )
    friends: RelationshipTo = RelationshipTo(
        "MypyPerson", "FRIEND_OF", cardinality=ZeroOrMore
    )
    managed_by: RelationshipFrom = RelationshipFrom(
        "MypyPerson", "MANAGES", cardinality=ZeroOrMore
    )


# Test 1: Property type inference
def test_property_types() -> None:
    """Verify that property access returns correct types."""
    person = MypyPerson()

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
    person = MypyPerson()

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
    name_prop: StringProperty = MypyPerson.name
    age_prop: IntegerProperty = MypyPerson.age
    height_prop: FloatProperty = MypyPerson.height
    active_prop: BooleanProperty = MypyPerson.active


# Test 4: Type errors should be caught
def test_type_errors() -> None:
    """These should produce type errors when checked with mypy."""
    person = MypyPerson()

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
    person = MypyPerson()
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
    person = MypyPerson()
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
    # Should type-check: NodeSet[MypyPerson] is correctly inferred
    all_people: list[MypyPerson] = MypyPerson.nodes.all()
    adults: "NodeSet[MypyPerson]" = MypyPerson.nodes.filter(age__gte=18)
    first_person: MypyPerson | None = MypyPerson.nodes.first()

    # Chained operations maintain the generic type
    filtered_people: "NodeSet[MypyPerson]" = MypyPerson.nodes.filter(
        age__gte=18
    ).exclude(active=False)
    ordered_people: "NodeSet[MypyPerson]" = MypyPerson.nodes.order_by("name")

    # get() returns MypyPerson, not Any
    specific_person: MypyPerson = MypyPerson.nodes.get(uid="123")
    maybe_person: MypyPerson | None = MypyPerson.nodes.get_or_none(uid="456")

    assert (
        all_people
        or adults
        or first_person
        or filtered_people
        or ordered_people
        or specific_person
        or maybe_person
    )


# Test 8: Relationship operations
def test_relationship_operations() -> None:
    """Verify relationship operations type-check correctly."""
    person = MypyPerson()
    company = MypyCompany()

    # Class-level access returns RelationshipDefinition
    company_def = MypyPerson.company
    friends_def = MypyPerson.friends

    # Instance-level access returns RelationshipManager with correct generic type
    # person.company is RelationshipManager[MypyCompany]
    # person.friends is RelationshipManager[MypyPerson]

    # Connect should accept the correct node type
    person.company.connect(company)
    person.friends.connect(person)

    # Type-safe relationship querying
    all_companies: list[MypyCompany] = person.company.all()
    single_company: MypyCompany | None = person.company.single()
    filtered_companies = person.company.filter(founded_year__gte=2000)

    all_friends: list[MypyPerson] = person.friends.all()
    single_friend: MypyPerson | None = person.friends.single()

    # is_connected returns bool
    is_connected: bool = person.company.is_connected(company)
    are_friends: bool = person.friends.is_connected(person)

    assert (
        company_def
        or friends_def
        or all_companies
        or single_company
        or filtered_companies
        or all_friends
        or single_friend
        or is_connected
        or are_friends
    )
