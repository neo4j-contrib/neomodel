==================
Extending neomodel
==================

When defining models that have a custom `__init__(self, ...)` method, you must always call `super()`::

    class Person(StructuredNode):
        name = StringProperty(unique_index=True)

        def __init__(self, name, *args, **kwargs):
            self.name = name

            super(Person, self).__init__(self, *args, **kwargs)
