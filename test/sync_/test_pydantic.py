from test._async_compat import mark_sync_test

import pytest

pytest.importorskip("pydantic")

from neomodel import (  # noqa: E402
    ArrayProperty,
    BooleanProperty,
    DateProperty,
    DateTimeProperty,
    EmailProperty,
    FloatProperty,
    IntegerProperty,
    JSONProperty,
    StringProperty,
    StructuredNode,
    UniqueIdProperty,
)
from neomodel.contrib.pydantic import (  # noqa: E402
    PydanticBridge,
    from_pydantic,
    pydantic_schema,
    to_pydantic,
    to_pydantic_model,
)


class PydanticPerson(PydanticBridge, StructuredNode):
    uid = UniqueIdProperty()
    name = StringProperty(required=True, max_length=120, help_text="Display name")
    email = EmailProperty()
    age = IntegerProperty()
    score = FloatProperty()
    role = StringProperty(choices={"admin": "Admin", "user": "User"})
    active = BooleanProperty(default=True)
    tags = ArrayProperty(StringProperty())
    created = DateTimeProperty(default_now=True)
    birthday = DateProperty()
    meta = JSONProperty()


def test_field_types_and_constraints():
    model = to_pydantic_model(PydanticPerson)
    fields = model.model_fields

    # Scalar property -> Python type mapping.
    assert fields["name"].annotation is str
    assert fields["age"].annotation == (int | None)
    assert fields["score"].annotation == (float | None)
    assert fields["active"].annotation is bool
    assert fields["tags"].annotation == (list[str] | None)

    from datetime import date, datetime

    # created has a default (default_now) so it is a non-optional datetime;
    # birthday has no default so it is optional.
    assert fields["created"].annotation is datetime
    assert fields["birthday"].annotation == (date | None)
    assert "meta" in fields  # JSONProperty -> Any

    schema = model.model_json_schema()
    # required=True -> required field with the max_length + help_text carried over.
    assert schema["required"] == ["name"]
    assert schema["properties"]["name"]["maxLength"] == 120
    assert schema["properties"]["name"]["description"] == "Display name"
    # choices -> enum.
    assert schema["properties"]["role"]["anyOf"][0]["enum"] == ["admin", "user"]


def test_defaults_are_carried_over():
    model = to_pydantic_model(PydanticPerson, with_element_id=False)
    instance = model(name="x")
    # Static default and callable default (UniqueIdProperty) both apply.
    assert instance.active is True
    assert isinstance(instance.uid, str) and len(instance.uid) == 32


def test_element_id_field_is_optional_and_toggleable():
    with_id = to_pydantic_model(PydanticPerson)
    without_id = to_pydantic_model(PydanticPerson, with_element_id=False)
    assert "element_id" in with_id.model_fields
    assert "element_id" not in without_id.model_fields


def test_include_and_exclude():
    only = to_pydantic_model(
        PydanticPerson, include={"name", "age"}, with_element_id=False
    )
    assert set(only.model_fields) == {"name", "age"}

    without = to_pydantic_model(PydanticPerson, exclude={"uid", "created"})
    assert "uid" not in without.model_fields and "created" not in without.model_fields

    with pytest.raises(ValueError, match="Unknown propert"):
        to_pydantic_model(PydanticPerson, include={"nope"})


def test_optional_mode_makes_everything_optional():
    patch = to_pydantic_model(PydanticPerson, optional=True, with_element_id=False)
    # No field is required in a PATCH-style model.
    assert patch.model_json_schema().get("required") is None
    assert patch().name is None  # a normally-required field is now optional


def test_use_db_aliases():
    class Aliased(PydanticBridge, StructuredNode):
        known_for = StringProperty(db_property="knownFor")

    model = to_pydantic_model(Aliased, use_db_aliases=True, with_element_id=False)
    assert model.model_fields["known_for"].alias == "knownFor"
    # populate_by_name is enabled, so the Python name still works.
    assert model(known_for="graphs").known_for == "graphs"
    # ...and so does the alias.
    assert model.model_validate({"knownFor": "graphs"}).known_for == "graphs"


def test_from_pydantic_builds_unsaved_node_and_ignores_extras():
    create_model = to_pydantic_model(
        PydanticPerson, exclude={"uid"}, with_element_id=True
    )
    dto = create_model(name="Bob", role="user", element_id="4:abc:1")
    node = from_pydantic(PydanticPerson, dto)
    assert isinstance(node, PydanticPerson)
    assert node.name == "Bob" and node.role == "user"
    assert node.element_id is None  # element_id is ignored; the node is unsaved

    # Also accepts a plain mapping.
    node2 = PydanticPerson.from_pydantic({"name": "Sue", "unknown": 1})
    assert node2.name == "Sue"


def test_pydantic_schema_helper():
    schema = pydantic_schema(PydanticPerson, include={"name"}, with_element_id=False)
    assert schema["properties"]["name"]["type"] == "string"


def test_generated_models_are_cached():
    assert to_pydantic_model(PydanticPerson) is to_pydantic_model(PydanticPerson)
    assert to_pydantic_model(PydanticPerson) is not to_pydantic_model(
        PydanticPerson, with_element_id=False
    )


def test_mixin_classmethods():
    # The mixin classmethods delegate to the module-level functions.
    assert PydanticPerson.to_pydantic_model() is to_pydantic_model(PydanticPerson)
    schema = PydanticPerson.pydantic_schema(include={"name"}, with_element_id=False)
    assert schema["properties"]["name"]["type"] == "string"


@mark_sync_test
def test_instance_round_trip_with_save():
    person = PydanticPerson(name="Alice", role="admin", tags=["a", "b"]).save()

    dto = person.to_pydantic()
    assert dto.name == "Alice"
    assert dto.role == "admin"
    assert dto.tags == ["a", "b"]
    # After save(), element_id is populated on the DTO.
    assert dto.element_id == person.element_id
    assert dto.uid == person.uid

    # Standalone function mirrors the mixin method.
    assert to_pydantic(person).element_id == person.element_id
