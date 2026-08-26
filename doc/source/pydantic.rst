.. _pydantic:

=====================
Pydantic bridge
=====================

``neomodel.contrib.pydantic`` turns a node class into a `Pydantic
<https://docs.pydantic.dev>`_ model for **validation, serialization and schema
export** - so you can put an API (FastAPI, Litestar, ...) or any I/O boundary on
top of your graph without hand-maintaining a second set of models.

The bridge is additive and non-breaking: it lives in ``contrib``, needs the
optional ``pydantic`` dependency, and is never imported by neomodel's core. It
also works unchanged with both the sync (``StructuredNode``) and async
(``AsyncStructuredNode``) APIs.

.. important::
   **neomodel is the schema authority.** The bridge is one-directional by
   design: your ``StructuredNode`` defines the model, and Pydantic models are
   *generated from* it - not the other way around. Graph-only information
   (indexes, uniqueness, ``db_property``, ``UniqueIdProperty``, and
   relationships) lives on the node class, because a plain Pydantic model has no
   way to express it. ``from_pydantic()`` (below) validates and populates an
   *existing* node class from a Pydantic instance or mapping; it does not derive
   a node class from a Pydantic model. If you want to start from Pydantic
   instead, treat that as one-off scaffolding to hand-edit, not a live source of
   truth.

.. note::
   **Scope.** This is the first version of the bridge: it maps a node's *scalar
   properties*. Relationships are not expanded yet.

Installation
============

.. code-block:: bash

    pip install neomodel[pydantic]

Two ways to use it
==================

Everything is available as **plain functions**::

    from neomodel.contrib.pydantic import (
        to_pydantic_model, to_pydantic, from_pydantic, pydantic_schema,
    )

    PersonModel = to_pydantic_model(Person)

or, if you prefer methods on your class, mix in ``PydanticBridge``::

    from neomodel import StructuredNode, StringProperty
    from neomodel.contrib.pydantic import PydanticBridge

    class Person(PydanticBridge, StructuredNode):
        name = StringProperty(required=True)

    PersonModel = Person.to_pydantic_model()

Both produce exactly the same result; the rest of this page uses the mixin.

Tutorial
========

Take a model with a representative mix of properties::

    from neomodel import (
        StructuredNode, StringProperty, IntegerProperty,
        EmailProperty, UniqueIdProperty, ArrayProperty, BooleanProperty,
    )
    from neomodel.contrib.pydantic import PydanticBridge

    class Person(PydanticBridge, StructuredNode):
        uid    = UniqueIdProperty()
        name   = StringProperty(required=True, max_length=120, help_text="Display name")
        email  = EmailProperty()
        age    = IntegerProperty()
        role   = StringProperty(choices={"admin": "Admin", "user": "User"})
        active = BooleanProperty(default=True)
        tags   = ArrayProperty(StringProperty())

Generate a model
-----------------

``to_pydantic_model()`` returns a normal Pydantic model class::

    PersonModel = Person.to_pydantic_model()

    PersonModel.model_fields.keys()
    # dict_keys(['uid', 'name', 'email', 'age', 'role', 'active', 'tags', 'element_id'])

The property metadata is carried across:

- ``required=True`` becomes a required field; everything else is optional
  (``... | None`` with a ``None`` default).
- ``default`` becomes a field default (callables such as ``UniqueIdProperty``
  become a ``default_factory``, so each instance still gets a fresh value).
- ``choices`` becomes a ``Literal`` / enum.
- ``max_length`` and ``help_text`` become field constraints and descriptions.
- ``element_id`` is added as a read-only ``str | None`` field (handy for
  responses - turn it off with ``with_element_id=False``).

Serialize an instance
---------------------

``to_pydantic()`` converts a node instance into a Pydantic instance - ready to
return from an endpoint or dump to JSON::

    alice = Person(name="Alice", role="admin", tags=["neo4j"]).save()

    dto = alice.to_pydantic()
    dto.model_dump()
    # {'uid': '…', 'name': 'Alice', 'email': None, 'age': None,
    #  'role': 'admin', 'active': True, 'tags': ['neo4j'],
    #  'element_id': '4:…:0'}

Build a node from validated input
---------------------------------

``from_pydantic()`` goes the other way. It accepts a Pydantic instance (or a
plain mapping), keeps only keys that match defined properties (so ``element_id``
and any extras are ignored), and returns an **unsaved** node - call ``.save()``
to persist it::

    incoming = PersonModel(name="Bob", role="user")   # already validated
    bob = Person.from_pydantic(incoming).save()

Export a JSON Schema
--------------------

``pydantic_schema()`` returns the model's JSON Schema - useful for OpenAPI docs,
contract tests, or generating TypeScript types for a frontend::

    Person.pydantic_schema()
    # {'title': 'PersonModel', 'type': 'object',
    #  'required': ['name'],
    #  'properties': {'name': {'type': 'string', 'maxLength': 120, ...},
    #                 'role': {'anyOf': [{'enum': ['admin', 'user'], ...}]}, ...}}

Tailoring the generated model
=============================

``to_pydantic_model()`` (and therefore ``pydantic_schema()``) takes a few
keyword options:

.. list-table::
   :header-rows: 1
   :widths: 22 78

   * - Option
     - Effect
   * - ``name``
     - Name of the generated model (default ``<NodeName>Model``).
   * - ``include``
     - Only these property names.
   * - ``exclude``
     - Drop these property names.
   * - ``optional``
     - Make **every** field optional with a ``None`` default - ideal for PATCH
       request bodies.
   * - ``with_element_id``
     - Add the ``element_id`` field (default ``True``; set ``False`` for input
       models).
   * - ``use_db_aliases``
     - Expose each field under its ``db_property`` as a Pydantic alias (and
       enable ``populate_by_name``).

For example, distinct models for creating, updating and returning a person::

    PersonCreate = Person.to_pydantic_model(name="PersonCreate",
                                            exclude={"uid"}, with_element_id=False)
    PersonPatch  = Person.to_pydantic_model(name="PersonPatch",
                                            optional=True, with_element_id=False)
    PersonOut    = Person.to_pydantic_model(name="PersonOut")

Generated models are cached per (class, options), so calling
``to_pydantic_model()`` repeatedly - for instance as a FastAPI
``response_model`` - is cheap.

Using it with FastAPI
=====================

This is the use case the bridge is built for. The node model is the single
source of truth; the request/response models are generated from it.

.. code-block:: python

    from fastapi import FastAPI, HTTPException
    from neomodel import (
        AsyncStructuredNode, StringProperty, IntegerProperty, UniqueIdProperty,
    )
    from neomodel.contrib.pydantic import PydanticBridge

    class Person(PydanticBridge, AsyncStructuredNode):
        uid  = UniqueIdProperty()
        name = StringProperty(required=True, max_length=120)
        age  = IntegerProperty()

    # Generated once at import time.
    PersonCreate = Person.to_pydantic_model(exclude={"uid"}, with_element_id=False)
    PersonPatch  = Person.to_pydantic_model(optional=True, with_element_id=False)
    PersonOut    = Person.to_pydantic_model()

    app = FastAPI()

    @app.post("/people", response_model=PersonOut)
    async def create_person(body: PersonCreate):
        # `body` is already validated by FastAPI/Pydantic.
        person = await Person.from_pydantic(body).save()
        return person.to_pydantic()

    @app.get("/people/{uid}", response_model=PersonOut)
    async def get_person(uid: str):
        try:
            person = await Person.nodes.get(uid=uid)
        except Person.DoesNotExist:
            raise HTTPException(status_code=404, detail="Not found")
        return person.to_pydantic()

    @app.patch("/people/{uid}", response_model=PersonOut)
    async def update_person(uid: str, body: PersonPatch):
        person = await Person.nodes.get(uid=uid)
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(person, field, value)
        await person.save()
        return person.to_pydantic()

What you get for free:

- Request bodies are validated *before* they reach Neo4j (type coercion,
  ``max_length``, ``choices``, required-field checks).
- The OpenAPI schema and Swagger UI reflect your graph model, including enums
  and constraints.
- ``PersonOut`` includes ``element_id``; ``PersonCreate``/``PersonPatch`` omit
  it - no duplicated model definitions to keep in sync.

Property mapping reference
==========================

.. list-table::
   :header-rows: 1
   :widths: 45 30 25

   * - neomodel property
     - Python type
     - Notes
   * - ``StringProperty``
     - ``str``
     - ``max_length`` → constraint
   * - ``StringProperty(choices=...)``
     - ``Literal[...]``
     - values become an enum
   * - ``IntegerProperty`` / ``FloatProperty``
     - ``int`` / ``float``
     -
   * - ``BooleanProperty``
     - ``bool``
     -
   * - ``DateProperty``
     - ``datetime.date``
     -
   * - ``DateTimeProperty`` (and format variants)
     - ``datetime.datetime``
     -
   * - ``EmailProperty``
     - ``str``
     - validated by neomodel on save
   * - ``UniqueIdProperty``
     - ``str``
     - ``default_factory`` (uuid)
   * - ``ArrayProperty(X)``
     - ``list[X]``
     -
   * - ``JSONProperty``
     - ``Any``
     -
   * - other / Neo4j-specific (e.g. ``PointProperty``)
     - ``Any``
     - see `Custom and Neo4j-specific property types`_
   * - ``element_id``
     - ``str | None``
     - read-only, opt-out via ``with_element_id``

Custom and Neo4j-specific property types
========================================

Most properties have a natural Python type (see the table above). A few
neomodel/Neo4j-specific types have no standard Pydantic equivalent - notably
``PointProperty`` from :ref:`spatial_properties`. These map to ``Any``, so the
field carries the raw neomodel value and will fail to JSON-serialize (for
example, in a FastAPI response). Two patterns handle them today.

.. note::
   The datetime family is **not** affected: ``DateTimeProperty``,
   ``DateTimeFormatProperty`` and ``DateTimeNeo4jFormatProperty`` all map to a
   plain ``datetime`` and serialize normally. This section is about types that
   fall through to ``Any``.

**1. Exclude the field, add a typed one with a converter.**

Generate the model for the scalar properties, then extend it with a
properly-typed field plus a ``before`` validator that converts the neomodel
value::

    from pydantic import field_validator
    from neomodel.contrib.pydantic import to_pydantic_model, to_pydantic

    PlaceScalars = to_pydantic_model(Place, exclude={"location"})

    class PlaceOut(PlaceScalars):
        location: dict | None = None

        @field_validator("location", mode="before")
        @classmethod
        def _point(cls, value):
            if value is None:
                return None
            return {"crs": value.crs, "coordinates": list(value.coords[0])}

**2. Feed your model back through the bridge.**

``to_pydantic()`` accepts an explicit ``model=`` - it reads each field off the
node with ``getattr`` and validates, so the ``before`` validator above does the
conversion. Use ``PlaceOut`` as your FastAPI ``response_model``::

    dto = to_pydantic(place, model=PlaceOut)
    dto.model_dump(mode="json")
    # {'name': 'HQ', 'location': {'crs': 'wgs-84', 'coordinates': [1.0, 2.0]}, ...}

On the way *in*, ``from_pydantic()`` does not convert custom types, so set the
attribute yourself after building the (unsaved) node::

    node = Place.from_pydantic(body)
    node.location = NeomodelPoint(tuple(body.location["coordinates"]), crs=body.location["crs"])
    node.save()

.. note::
   A future release will let you register such mappings once - e.g.
   ``register_property_type(PointProperty, ...)`` - instead of repeating them per
   model.

Building nodes with a specific datetime (or other) type
-------------------------------------------------------

``from_pydantic()`` passes each value straight to the node constructor; the
database-specific conversion happens in the property's ``deflate`` at
``save()`` time. So the *neomodel-side* type is simply whichever property you
declared - you never repeat it on the Pydantic side.

Datetimes are the common case. Whether the node stores its datetime as an epoch
(``DateTimeProperty``), a formatted string (``DateTimeFormatProperty``) or the
native Neo4j type (``DateTimeNeo4jFormatProperty``), the generated field is a
plain ``datetime`` and ``from_pydantic(...).save()`` works unchanged - the
property decides how it is persisted::

    from datetime import datetime, timezone

    class Meeting(StructuredNode):
        starts = DateTimeNeo4jFormatProperty()   # or DateTimeProperty / DateTimeFormatProperty

    MeetingModel = to_pydantic_model(Meeting, with_element_id=False)
    body = MeetingModel(starts=datetime(2024, 5, 1, 12, tzinfo=timezone.utc))
    Meeting.from_pydantic(body).save()

Pydantic coerces ISO-8601 strings into ``datetime`` during validation (the field
is ``datetime``-typed), so string input from an API works too. The only thing to
watch is a value the property's ``deflate`` does not accept - for instance a Unix
timestamp ``int`` where a ``datetime`` is expected. Convert it with a
``field_validator`` on the Pydantic model, or after ``from_pydantic()``::

    node = Meeting.from_pydantic(body)
    node.starts = datetime.fromtimestamp(body.starts, tz=timezone.utc)
    node.save()

Limitations (v1)
================

- **Scalar properties only.** Relationships are not expanded into nested models
  yet.
- ``EmailProperty`` maps to ``str`` (neomodel already validates the address on
  ``save()``); this keeps the ``neomodel[pydantic]`` extra lightweight
  and prevents a validation clash on read.
- ``SemiStructuredNode``'s free-form extra keys are not reflected in the
  generated model.
