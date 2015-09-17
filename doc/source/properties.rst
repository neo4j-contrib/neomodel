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

Choices
=======

You can specify a list of valid values for a `StringProperty` using choices::

    class Person(StructuredNode):
        SEXES = (
            ('M', 'Male'),
            ('F', 'Female')
        )
        sex = StringProperty(required=True, choices=SEXES)

    tim = Person(sex='M').save()
    tim.sex # M
    tim.get_sex_display() # 'Male'

The value will be checked both when saved and loaded from neo4j.

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
    
Independent database property name
================================

You can specify an independent property name with 'db_property', which is used on database level. It behaves like Django's 'db_column'.
This is useful for e.g. hiding graph properties behind a python property::

    class Person(StructuredNode):
        name_ = StringProperty(db_property='name')
        
        @property
        def name(self):
            return self.name_.lower() if self.name_ else None

        @name.setter
        def name(self, value):
            self.name_ = value

