==============
Property types
==============

The following properties are available on nodes and relationships:

==============================================  ==============================================
:class:`~neomodel.properties.AliasProperty`     :class:`~neomodel.properties.IntegerProperty`
:class:`~neomodel.properties.ArrayProperty`     :class:`~neomodel.properties.JSONProperty`
:class:`~neomodel.properties.BooleanProperty`   :class:`~neomodel.properties.RegexProperty`
:class:`~neomodel.properties.DateProperty`      :class:`~neomodel.properties.StringProperty`
:class:`~neomodel.properties.DateTimeProperty`  :class:`~neomodel.properties.UniqueIdProperty`
:class:`~neomodel.properties.FloatProperty`
==============================================  ==============================================


Defaults
========

Default values can be specified for any property, even as the result of a 
:term:`function` or other callable object::

        from uuid import uuid4
        my_id = StringProperty(unique_index=True, default=uuid4)

And in terms of a :term:`function` or :term:`lambda`::

        my_datetime = DateTimeProperty(default=lambda: datetime.now(pytz.utc))

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
Neomodel supports arrays via the `ArrayProperty` class and a list element type 
can optionally be provided as the first argument::

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

The *DateTimeProperty* accepts `datetime.datetime` objects of any timezone and stores them as a UTC epoch value.
These epoch values are inflated to datetime.datetime objects with the UTC timezone set.

The *DateProperty* accepts datetime.date objects which are stored as a string property 'YYYY-MM-DD'.

The `default_now` parameter specifies the current time as the default value::

        created = DateTimeProperty(default_now=True)

Enforcing a specific timezone is done by setting the config variable` NEOMODEL_FORCE_TIMEZONE=1`.

Other properties
================

* `EmailProperty` - validate emails (via a regex).
* `RegexProperty` - passing in a validator regex: `RegexProperty(expression=r'\d\w')`
* `NormalProperty` - use one method (normalize) to inflate and deflate.


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
