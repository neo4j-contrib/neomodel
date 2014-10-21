==============
Property types
==============

The following properties are available on nodes and relationships::

    StringProperty, IntegerProperty, FloatProperty, BooleanProperty, ArrayProperty

    DateProperty, DateTimeProperty, JSONProperty, AliasProperty

Defaults
========

*Default values* you may provide a default value to any property, this can also be a function or any callable::

        from uuid import uuid4
        my_id = StringProperty(unique_index=True, default=uuid4)

You may provide arguments using a wrapper function or lambda::

        my_datetime = DateTimeProperty(default=lambda: datetime.now(pytz.utc))

Dates and times
===============

The *DateTimeProperty* accepts datetime.datetime objects of any timezone and stores them as a UTC epoch value.
These epoch values are inflated to datetime.datetime objects with the UTC timezone set. If you want neomodel
to raise an exception on receiving a datetime without a timezone you set the env var NEOMODEL_FORCE_TIMEZONE=1.

The *DateProperty* accepts datetime.date objects which are stored as a string property 'YYYY-MM-DD'.

Aliasing properties
===================

Allows aliasing to other properties can be useful to provide 'magic' behaviour, (only supported on `StructuredNodes`)::

    class Person(StructuredNode):
        full_name = StringProperty(index=True)
        name = AliasProperty(to='full_name')

    Person.nodes.filter(name='Jim') # just works
