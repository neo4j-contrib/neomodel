.. _property_types:

==============
Property types
==============

The following properties are available on nodes and relationships:

====================================================  ===========================================================
:class:`~neomodel.properties.AliasProperty`           :class:`~neomodel.properties.IntegerProperty`
:class:`~neomodel.properties.ArrayProperty`           :class:`~neomodel.properties.JSONProperty`
:class:`~neomodel.properties.BooleanProperty`         :class:`~neomodel.properties.RegexProperty`
:class:`~neomodel.properties.DateProperty`            :class:`~neomodel.properties.StringProperty` (:ref:`Notes <properties_notes>`)
:class:`~neomodel.properties.DateTimeProperty`        :class:`~neomodel.properties.UniqueIdProperty`
:class:`~neomodel.properties.DateTimeFormatProperty`  :class:`~neomodel.contrib.spatial_properties.PointProperty`
:class:`~neomodel.properties.FloatProperty`           \
====================================================  ===========================================================


Naming Convention
=================
You can follow standard
`Python variable naming conventions <https://www.python.org/dev/peps/pep-0008/#function-and-variable-names>`_ to name
an entity's properties but please note that **a property name should not begin with an underscore (_) character**.

Doing so leads to `unpredictable results <https://github.com/neo4j-contrib/neomodel/issues/279#issue-267468010>`_.

By design, ``neomodel.StructuredNode`` derived entities reserve a number of *protected* variables to perform quick
look-up operations. The names of those variables begin with an underscore and therefore any member variable that
begins with this character is excluded from further processing.


Defaults
========

Default values can be specified for any property, even as the result of a 
:term:`function` or other callable object::

        from uuid import uuid4
        my_id = StringProperty(unique_index=True, default=uuid4)

And in terms of a :term:`function` or :term:`lambda`::

        my_datetime = DateTimeProperty(default=lambda: datetime.now(pytz.utc))

Mandatory / Optional Properties
===============================
Whether the value of a property is absolutely essential for an entity's existence or can be left undefined is determined
by the ``required`` parameter that applies to all properties.

This is a boolean parameter that defaults to ``False`` and makes an entity's properties *optional* by default.

Setting ``required=True`` makes the property mandatory. Mandatory properties cannot have default values and setting
both ``required=True, default`` will result in a ``ValueError`` exception.

It is worth noting here that ``required=False`` means that the property's value can also be ``None`` **in addition** to
a valid valud. A value of ``None`` is **different** than a value of ``""`` and this can sometimes lead to logical
errors.

For example::

    class Person(StructuredNode):
        uid = UniqueIdProperty()
        full_name = StringProperty(required = True)
        email = EmailProperty()

Here ``Person.full_name`` is mandatory but ``Person.email`` is optional. With this definition, the following would
fail::

    some_person = Person().save()

Because ``full_name == None`` but ``full_name`` has been marked as ``required`` for the definition of ``Person``.

Notice here that the following would fail too::

    some_person = Person(full_name="Thomas Edison", email="").save()

In this case the ``EmailProperty`` would raise a ``ValueError`` to complain that ``""`` does not look like a valid email
address.

The ``email`` property **is** optional here which means that its value can be left undefined (``None``), **not** that
its set of valid values includes the empty string.

Choices
=======

Choices can be specified as a mapping (dict) of valid values for a :class:`~neomodel.properties.StringProperty`
using the ``choices`` argument. The mapping's values are used when displaying information to users::

    class Person(StructuredNode):
        SEXES = {'F': 'Female', 'M': 'Male', 'O': 'Other'}
        sex = StringProperty(required=True, choices=SEXES)

    tim = Person(sex='M').save()
    tim.sex # M
    tim.get_sex_display() # 'Male'

The value's validity will be checked both when saved and loaded from the database.

Array Properties
================
Neomodel supports neo4j's arrays via the `ArrayProperty` class and the class for each list element can optionally be
provided as the first argument::
   
    class Person(StructuredNode):
        names = ArrayProperty(StringProperty(), required=True)

    bob = Person(names=['bob', 'rob', 'robert']).save()

In this example each element in the list is deflated to a string prior to being persisted.

Unique Identifiers
==================
All nodes in neo4j have an internal id (accessible by the 'id' property in neomodel)
however these should not be used by an application.
Neomodel provides the `UniqueIdProperty` to generate unique identifiers for nodes (with a unique index)::

    class Person(StructuredNode):
        uid = UniqueIdProperty()

    Person.nodes.get(uid='a12df...')

Dates and times
===============

The *DateTimeProperty* accepts ``datetime.datetime`` objects of any timezone and stores them as a UTC epoch value.
These epoch values are inflated to datetime.datetime objects with the UTC timezone set.

Similarly, the *DateTimeFormatProperty* accepts ``datetime.datetime`` objects but stores them
as a user defined formatted date string. The pattern is set by the ``format`` argument which defaults to "%Y-%m-%d".

In the following example the datetime will be stored as 'YYYY-MM-DD HH:mm:ss'::
      
        created = DateTimeFormatProperty(format="%Y-%m-%d %H:%M:%S")

The *DateProperty* accepts datetime.date objects which are stored as a string property 'YYYY-MM-DD'.

In all of the above, the `default_now` parameter specifies the "current time" (the time a "write" operation takes place)
as the default value::

        created = DateTimeProperty(default_now=True)

Enforcing a specific timezone is done by setting the config variable ``NEOMODEL_FORCE_TIMEZONE=1``.


Other properties
================

* `EmailProperty` - validate emails (via a regex).
* `RegexProperty` - passing in a validator regex: `RegexProperty(expression=r'\d\w')`
* `NormalProperty` - use one method (normalize) to inflate and deflate.
* `PointProperty` - store and validate :ref:`spatial_properties`

Aliasing properties
===================

Allows aliasing to other properties which can be useful to provide 'magic' behaviour, (only supported on `StructuredNodes`)::

    class Person(StructuredNode):
        full_name = StringProperty(index=True)
        name = AliasProperty(to='full_name')

    Person.nodes.filter(name='Jim') # just works

Independent database property name
==================================

You can specify an independent property name with 'db_property', which is used at the database level. It behaves like Django's 'db_column'.
This is useful when hiding graph properties behind a python property::

    class Person(StructuredNode):
        name_ = StringProperty(db_property='name')

        @property
        def name(self):
            return self.name_.lower() if self.name_ else None

        @name.setter
        def name(self, value):
            self.name_ = value


.. _properties_notes:

Notes
=====

This section groups together special notes for specific data types.


``StringProperty``
------------------

1. One needs to be extremely careful with very long strings that are also indexed.
    1. Neo4j imposes an internal hard limit of 4039 **bytes** to properties of type string. This is **not the same** as
       the length of a UTF-8 string **in characters**, because each character in a UTF-8 string might be represented
       by more than one bytes.
    2. Internally, Neo4j will **truncate** a string so that its **byte** length is not longer than 4039 but it will not
       raise an exception. Consequently, if a `neomodel.StringProperty()` happens to run much longer than this limit,
       it will be silently truncated. The rest of the string will be dropped and the next time the entity is read from
       the database it will appear to be incomplete.
    3. This can also lead to a `UniqueException` if two strings differ **after** the 4039 byte mark.
    4. For more information please see `here <https://github.com/neo4j/neo4j/issues/12076#issuecomment-438286444>`_.
