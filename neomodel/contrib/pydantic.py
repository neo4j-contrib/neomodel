"""
Pydantic bridge (``neomodel.contrib.pydantic``).

Generate a `Pydantic <https://docs.pydantic.dev>`_ model from a neomodel node
class for validation, serialization and schema export - the pieces most people
need when putting an API (FastAPI, Litestar, ...) or any I/O boundary on top of
a graph model, without hand-maintaining a parallel set of DTOs.

The bridge is *additive and non-breaking*: it lives in ``contrib``, requires the
optional ``pydantic`` dependency (``pip install neomodel[pydantic]``), and is
never imported by neomodel's core. It is also world-agnostic - it introspects a
class via its public ``defined_properties()`` / ``__properties__`` API, so it
works unchanged on both ``StructuredNode`` and ``AsyncStructuredNode``.

Scope (v1): scalar properties only. Relationships are not expanded; that is left
to a later iteration.

Public API
----------
- :func:`to_pydantic_model` - build (and cache) a Pydantic model *class* from a
  node class.
- :func:`to_pydantic` - convert a node *instance* into a Pydantic instance.
- :func:`from_pydantic` - build an (unsaved) node instance from a Pydantic
  instance or mapping.
- :func:`pydantic_schema` - the JSON Schema of the generated model.
- :class:`PydanticBridge` - optional mixin exposing the above as methods
  (``MyNode.to_pydantic_model()``, ``instance.to_pydantic()``, ...).
"""

from __future__ import annotations

import weakref
from datetime import date, datetime
from typing import Any, Iterable, Literal, Optional

try:
    from pydantic import BaseModel, ConfigDict, Field, create_model
except ImportError as exc:  # pragma: no cover - exercised via install extras
    raise ImportError(
        "neomodel's Pydantic bridge requires Pydantic v2. "
        "Install it with `pip install neomodel[pydantic]`."
    ) from exc

from neomodel.properties import (
    ArrayProperty,
    BooleanProperty,
    DateProperty,
    DateTimeFormatProperty,
    DateTimeNeo4jFormatProperty,
    DateTimeProperty,
    FloatProperty,
    IntegerProperty,
    JSONProperty,
    NormalizedProperty,
    Property,
    RegexProperty,
    StringProperty,
    UniqueIdProperty,
)

__all__ = [
    "to_pydantic_model",
    "to_pydantic",
    "from_pydantic",
    "pydantic_schema",
    "PydanticBridge",
]

# Cache of generated model classes, keyed by node class then by option signature.
_MODEL_CACHE: "weakref.WeakKeyDictionary[type, dict]" = weakref.WeakKeyDictionary()


def _python_type(prop: Property) -> Any:
    """Map a neomodel property to the Python type a Pydantic field should use.

    Ordered from most- to least-specific so subclasses (EmailProperty,
    UniqueIdProperty, ...) resolve before their bases.
    """
    if isinstance(prop, ArrayProperty):
        inner = (
            _python_type(prop.base_property) if prop.base_property is not None else Any
        )
        return list[inner]  # type: ignore[valid-type]
    if isinstance(prop, UniqueIdProperty):
        return str
    # EmailProperty maps to plain ``str`` (neomodel validates the address on
    # save); using pydantic's EmailStr would pull in the heavier email-validator
    # dependency, which the lightweight ``neomodel[pydantic]`` extra avoids.
    if isinstance(prop, StringProperty):
        if prop.choices:
            return Literal[tuple(prop.choices.keys())]
        return str
    if isinstance(prop, (RegexProperty, NormalizedProperty)):
        return str
    if isinstance(prop, BooleanProperty):
        return bool
    if isinstance(prop, IntegerProperty):
        return int
    if isinstance(prop, FloatProperty):
        return float
    if isinstance(
        prop,
        (DateTimeProperty, DateTimeFormatProperty, DateTimeNeo4jFormatProperty),
    ):
        return datetime
    if isinstance(prop, DateProperty):
        return date
    if isinstance(prop, JSONProperty):
        return Any
    return Any  # pragma: no cover - defensive default for unknown property types


def _field_definition(
    prop: Property, *, optional: bool, use_db_aliases: bool
) -> tuple[Any, Any]:
    """Return a ``(type, FieldInfo)`` pair for :func:`pydantic.create_model`."""
    py_type = _python_type(prop)
    field_kwargs: dict[str, Any] = {}
    if prop.help_text:
        field_kwargs["description"] = prop.help_text
    if isinstance(prop, StringProperty) and prop.max_length:
        field_kwargs["max_length"] = prop.max_length
    if use_db_aliases and prop.db_property:
        field_kwargs["alias"] = prop.db_property

    # ``optional`` (PATCH-style) forces every field nullable with a None default.
    if optional or not (prop.required or prop.has_default):
        return (Optional[py_type], Field(default=None, **field_kwargs))
    if prop.required:
        return (py_type, Field(..., **field_kwargs))
    # Has a default: callables become default_factory (e.g. UniqueIdProperty).
    default = prop.default
    if callable(default):
        return (py_type, Field(default_factory=default, **field_kwargs))
    return (py_type, Field(default=default, **field_kwargs))


def _select_properties(
    node_cls: Any,
    include: Iterable[str] | None,
    exclude: Iterable[str] | None,
) -> dict[str, Property]:
    props: dict[str, Property] = node_cls.defined_properties(aliases=False, rels=False)
    if include is not None:
        include = set(include)
        unknown = include - set(props)
        if unknown:
            raise ValueError(
                f"Unknown propert{'y' if len(unknown) == 1 else 'ies'} in include: "
                f"{sorted(unknown)}"
            )
        props = {name: prop for name, prop in props.items() if name in include}
    if exclude is not None:
        exclude = set(exclude)
        props = {name: prop for name, prop in props.items() if name not in exclude}
    return props


def to_pydantic_model(
    node_cls: Any,
    *,
    name: str | None = None,
    include: Iterable[str] | None = None,
    exclude: Iterable[str] | None = None,
    optional: bool = False,
    with_element_id: bool = True,
    use_db_aliases: bool = False,
) -> type[BaseModel]:
    """Build a Pydantic model class mirroring ``node_cls``'s scalar properties.

    :param node_cls: a ``StructuredNode`` / ``AsyncStructuredNode`` subclass.
    :param name: name for the generated model (default ``<NodeName>Model``).
    :param include: only these property names (default: all scalar properties).
    :param exclude: drop these property names.
    :param optional: make every field optional with a ``None`` default - handy
        for PATCH request bodies.
    :param with_element_id: add a read-only ``element_id: str | None`` field
        (useful for responses; set ``False`` for create/patch input models).
    :param use_db_aliases: expose each field under its ``db_property`` as a
        Pydantic alias (and enable ``populate_by_name``).

    The result is cached per (node class, options), so it is cheap to call
    repeatedly (e.g. as a FastAPI ``response_model``).
    """
    key = (
        name,
        tuple(sorted(include)) if include is not None else None,
        tuple(sorted(exclude)) if exclude is not None else None,
        optional,
        with_element_id,
        use_db_aliases,
    )
    cache = _MODEL_CACHE.setdefault(node_cls, {})
    if key in cache:
        return cache[key]

    fields: dict[str, Any] = {}
    for prop_name, prop in _select_properties(node_cls, include, exclude).items():
        fields[prop_name] = _field_definition(
            prop, optional=optional, use_db_aliases=use_db_aliases
        )
    if with_element_id:
        fields["element_id"] = (Optional[str], Field(default=None))

    config = ConfigDict(populate_by_name=True) if use_db_aliases else None
    model = create_model(
        name or f"{node_cls.__name__}Model",
        __config__=config,
        **fields,
    )
    cache[key] = model
    return model


def to_pydantic(
    node: Any, *, model: type[BaseModel] | None = None, **kwargs: Any
) -> BaseModel:
    """Convert a node *instance* into a Pydantic instance.

    Pass an explicit ``model`` to reuse a model built elsewhere, or let the
    bridge build/cache one from ``type(node)`` using the same keyword options as
    :func:`to_pydantic_model`.
    """
    if model is None:
        model = to_pydantic_model(type(node), **kwargs)
    data = {
        field_name: getattr(node, field_name, None)
        for field_name in model.model_fields
        if field_name != "element_id"
    }
    if "element_id" in model.model_fields:
        data["element_id"] = node.element_id
    return model.model_validate(data)


def from_pydantic(node_cls: Any, data: Any) -> Any:
    """Build an **unsaved** node instance from a Pydantic instance or mapping.

    Only keys matching defined properties are used; anything else (e.g.
    ``element_id``) is ignored. Call ``.save()`` on the result to persist it.
    """
    if isinstance(data, BaseModel):
        values = data.model_dump()
    else:
        values = dict(data)
    props = node_cls.defined_properties(aliases=False, rels=False)
    kwargs = {name: value for name, value in values.items() if name in props}
    return node_cls(**kwargs)


def pydantic_schema(node_cls: Any, **kwargs: Any) -> dict[str, Any]:
    """Return the JSON Schema of the generated model (accepts the same keyword
    options as :func:`to_pydantic_model`)."""
    return to_pydantic_model(node_cls, **kwargs).model_json_schema()


class PydanticBridge:
    """Optional mixin exposing the bridge functions as methods.

    ::

        class Person(PydanticBridge, StructuredNode):
            name = StringProperty(required=True)

        PersonOut = Person.to_pydantic_model()
        dto = alice.to_pydantic()
        node = Person.from_pydantic(dto)
    """

    @classmethod
    def to_pydantic_model(cls, **kwargs: Any) -> type[BaseModel]:
        return to_pydantic_model(cls, **kwargs)

    @classmethod
    def from_pydantic(cls, data: Any) -> Any:
        return from_pydantic(cls, data)

    @classmethod
    def pydantic_schema(cls, **kwargs: Any) -> dict[str, Any]:
        return pydantic_schema(cls, **kwargs)

    def to_pydantic(
        self, *, model: type[BaseModel] | None = None, **kwargs: Any
    ) -> BaseModel:
        return to_pydantic(self, model=model, **kwargs)
