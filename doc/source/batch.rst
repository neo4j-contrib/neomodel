=====================
Batch node operations
=====================

neomodel follows Django's pattern where both read **and write** operations live on the
``NodeSet`` (accessible via ``MyNode.nodes``).  This keeps the API consistent with the
query interface and makes it easy to chain filters with creation.


NodeSet methods (recommended)
------------------------------

Single-node methods
~~~~~~~~~~~~~~~~~~~

These methods create or retrieve **one node** at a time and follow the Django
``objects.create()`` / ``objects.get_or_create()`` / ``objects.update_or_create()``
conventions.

``nodes.create(**kwargs)``
^^^^^^^^^^^^^^^^^^^^^^^^^^
Create a single node and return it::

    class Person(StructuredNode):
        name = StringProperty(required=True)
        age = IntegerProperty()

    tim = await Person.nodes.create(name="Tim", age=83)

``nodes.get_or_create(defaults=None, **kwargs)``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Look up a node by ``**kwargs``.  If it does not exist, create it (merging
``defaults`` into the creation properties, but **not** using them for lookup).
Returns ``(node, created)``::

    # first call → created=True
    tim, created = await Person.nodes.get_or_create(name="Tim", defaults={"age": 83})
    assert created is True

    # second call → created=False, existing node returned
    tim2, created = await Person.nodes.get_or_create(name="Tim", defaults={"age": 99})
    assert created is False
    assert tim2.age == 83   # age was NOT changed because the node already existed

``nodes.update_or_create(defaults=None, **kwargs)``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Like ``get_or_create``, but **updates** the matched node with ``defaults`` when it
already exists.  Returns ``(node, created)``::

    tim, created = await Person.nodes.update_or_create(
        name="Tim",
        defaults={"age": 99},
    )
    assert tim.age == 99  # updated on match, or set on creation


Bulk methods
~~~~~~~~~~~~

These methods accept any number of property dicts and process them in a single
operation.

``nodes.bulk_create(*props, **kwargs)``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Create multiple nodes at once.  A CREATE query is issued for each dict::

    with db.transaction:
        people = await Person.nodes.bulk_create(
            {"name": "Tim",  "age": 83},
            {"name": "Bob",  "age": 23},
            {"name": "Jill", "age": 34},
        )

.. note::
    ``bulk_create`` also supports the ``relationship`` parameter (see
    `Relationships and Relationship Properties`_ below).

``nodes.bulk_create_or_update(*props, **kwargs)``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Atomically create or update multiple nodes.  The **required** and **unique**
properties are used as keys; all other properties are updated on match::

    class Person(StructuredNode):
        name = StringProperty(required=True)
        age = IntegerProperty()

    people = await Person.nodes.bulk_create_or_update(
        {"name": "Tim",  "age": 83},  # created
        {"name": "Bob",  "age": 23},  # created
        {"name": "Jill", "age": 34},  # created
    )

    updated = await Person.nodes.bulk_create_or_update(
        {"name": "Tim",  "age": 73},  # updated
        {"name": "Bob",  "age": 35},  # updated
        {"name": "Jane", "age": 24},  # created
    )


Custom Merge Keys
~~~~~~~~~~~~~~~~~
``nodes.get_or_create``, ``bulk_create_or_update``, and the deprecated
``get_or_create()`` / ``create_or_update()`` classmethods accept a ``merge_by``
parameter to override which properties are used as lookup keys.

For the single-node ``nodes.get_or_create``, ``merge_by`` is a list of kwarg names
to use as the lookup key (defaults to all kwargs)::

    class User(StructuredNode):
        username = StringProperty(required=True)
        email = StringProperty(required=True)
        full_name = StringProperty()
        age = IntegerProperty()

    # Default: look up by both username and email
    user, created = await User.nodes.get_or_create(
        username="johndoe", email="john@example.com", age=30
    )

    # Custom: look up by email only; username and age are creation-only via defaults
    user, created = await User.nodes.get_or_create(
        email="john@example.com",
        merge_by=["email"],
        defaults={"username": "johndoe", "age": 30},
    )

    # Custom: look up by username only
    user, created = await User.nodes.get_or_create(
        username="johndoe",
        email="john.doe@newcompany.com",
        merge_by=["username"],
    )

For ``bulk_create_or_update`` and the deprecated classmethods, ``merge_by`` is a dict
with ``keys`` (required) and an optional ``label``::

    # Custom: merge by email only
    users = await User.nodes.bulk_create_or_update(
        {"username": "johndoe", "email": "john@example.com", "age": 31},
        merge_by={"keys": ["email"]},
    )

    # Custom: merge by username only, with explicit label
    users = await User.nodes.bulk_create_or_update(
        {"username": "johndoe", "email": "john.doe@newcompany.com", "age": 32},
        merge_by={"label": "User", "keys": ["username"]},
    )

The deprecated ``get_or_create()`` classmethod uses the same dict form::

    users = User.get_or_create(
        {"username": "johndoe", "email": "john@example.com", "age": 31},
        merge_by={"keys": ["email"]},
    )

``merge_by`` (dict form) accepts:

- ``keys`` – list of property names to use as the merge key(s) (required).
- ``label`` – Neo4j label to match against (optional; defaults to the node's
  inherited labels).

Only explicitly provided properties will be updated on the node when the key
matches::

    node = await NodeWithDefaultProp.nodes.bulk_create_or_update({"name": "Tania", "age": 20})
    assert node[0].age == 20

    node = await NodeWithDefaultProp.nodes.bulk_create_or_update({"name": "Tania", "other_prop": "other"})
    assert node[0].age == 20   # age is NOT reset to the default of 30 — it was not provided


.. attention::
    When using ``UniqueIdProperty`` (which is both unique and has a default value),
    omitting it will generate a fresh random UID and therefore **create** a new node
    instead of matching the existing one.  Always pass the UID explicitly if you want
    to update an existing node.
    (`GitHub issue #807 <https://github.com/neo4j-contrib/neomodel/issues/807>`_)


Relationships and Relationship Properties
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The bulk methods support the ``relationship`` parameter to scope the operation within
a specific relationship context, and ``rel_props`` to set properties on that
relationship::

    from datetime import datetime, UTC

    class PetsRel(StructuredRel):
        since = DateTimeProperty()
        notes = StringProperty()

    class Dog(StructuredNode):
        name = StringProperty(required=True)
        owner = RelationshipTo("Person", "OWNS", model=PetsRel)

    class Person(StructuredNode):
        name = StringProperty(unique_index=True)
        pets = RelationshipFrom("Dog", "OWNS", model=PetsRel)

    charlie, _ = await Person.nodes.get_or_create(name="Charlie")
    since_date = datetime(2019, 3, 10, tzinfo=UTC)

    dogs = await Dog.nodes.bulk_create_or_update(
        {"name": "Spot"},
        relationship=charlie.pets,
        rel_props={"since": since_date, "notes": "First adoption"},
    )

The same pattern applies to ``bulk_create``::

    diana, _ = await Person.nodes.get_or_create(name="Diana")

    dogs = await Dog.nodes.bulk_create(
        {"name": "Bella"},
        {"name": "Charlie"},
        {"name": "Daisy"},
        relationship=diana.pets,
        rel_props={"since": datetime(2022, 6, 15, tzinfo=UTC), "notes": "Rescue dogs"},
    )

.. note::
    When using the bulk merge methods with a ``relationship``, if a node is matched
    and updated, a **new** relationship is created with the provided ``rel_props``.
    The old relationship (if any) will remain.


get_or_create with a relationship (scoped uniqueness)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The deprecated ``get_or_create()`` classmethod supports a ``relationship`` parameter to
enforce per-owner uniqueness::

    class Dog(StructuredNode):
        name = StringProperty(required=True)
        owner = RelationshipTo("Person", "owner")

    class Person(StructuredNode):
        name = StringProperty(unique_index=True)
        pets = RelationshipFrom("Dog", "owner")

    bob, _ = await Person.nodes.get_or_create(name="Bob")
    bobs_gizmo = await Dog.get_or_create({"name": "Gizmo"}, relationship=bob.pets)

    tim, _ = await Person.nodes.get_or_create(name="Tim")
    tims_gizmo = await Dog.get_or_create({"name": "Gizmo"}, relationship=tim.pets)

    assert bobs_gizmo[0] != tims_gizmo[0]   # different Gizmos for different owners


Lazy mode
~~~~~~~~~
All bulk methods accept ``lazy=True``, which makes the query return element IDs
instead of fully hydrated nodes (useful when you only need IDs)::

    element_ids = await Person.nodes.bulk_create(
        {"name": "Tim", "age": 83},
        lazy=True,
    )


----

Deprecated class-level methods
--------------------------------

.. deprecated::
    The class-level ``create()``, ``get_or_create()``, and ``create_or_update()``
    methods on ``StructuredNode`` are **deprecated** and will be removed in a future
    release.  Use the ``NodeSet`` methods on ``MyNode.nodes`` instead.

+------------------------------------------+--------------------------------------------------+
| Old (deprecated)                         | New (recommended)                                |
+==========================================+==================================================+
| ``Person.create({"name": "Tim"})``       | ``await Person.nodes.bulk_create({"name": ...})``|
+------------------------------------------+--------------------------------------------------+
| ``Person.get_or_create({"name": ...})``  | ``await Person.nodes.get_or_create(name=...)``   |
+------------------------------------------+--------------------------------------------------+
| ``Person.create_or_update({"name": ...})``| ``await Person.nodes.bulk_create_or_update(...)``|
+------------------------------------------+--------------------------------------------------+

For single-node creation with a ``created`` flag, prefer the new Django-style methods:

+--------------------------------------------------+-----------------------------------------+
| New single-node method                           | Returns                                 |
+==================================================+=========================================+
| ``await Person.nodes.create(name=...)``          | ``node``                                |
+--------------------------------------------------+-----------------------------------------+
| ``await Person.nodes.get_or_create(name=...)``   | ``(node, created: bool)``               |
+--------------------------------------------------+-----------------------------------------+
| ``await Person.nodes.update_or_create(name=...)``| ``(node, created: bool)``               |
+--------------------------------------------------+-----------------------------------------+
