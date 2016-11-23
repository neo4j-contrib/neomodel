==================
Extending neomodel
==================

Inheritance
-----------
You may want to create a 'base node' classes which extends the functionality which neomodel provides
(such as `neomodel.contrib.SemiStructuredNode`).

Or just have common methods and properties you want to share.
This can be achieved using the `__abstract_node__` property on any base classes you wish to inherit from::

    class User(StructuredNode):
        __abstract_node__ = True
        name = StringProperty(unique_index=True)

    class Shopper(User):
        balance = IntegerProperty(index=True)

        def credit_account(self, amount):
            self.balance = self.balance + int(amount)
            self.save()

Mixins
------
You can use mixins to share the functionality between nodes classes::

    class UserMixin(object):
        name = StringProperty(unique_index=True)
        password = StringProperty()

    class CreditMixin(object):
        balance = IntegerProperty(index=True)

        def credit_account(self, amount):
            self.balance = self.balance + int(amount)
            self.save()

    class Shopper(StructuredNode, User, CreditMixin):
        pass

    jim = Shopper(name='jimmy', balance=300).save()
    jim.credit_account(50)

Make sure your mixins *dont* inherit from `StructuredNode` and your concrete class does.

Overriding the StructuredNode constructor
-----------------------------------------

When defining classes that have a custom `__init__(self, ...)` method,
you must always call `super()` for the neomodel magic to work::

    class Person(StructuredNode):
        name = StringProperty(unique_index=True)

        def __init__(self, name, *args, **kwargs):
            self.name = name

            super(Person, self).__init__(self, *args, **kwargs)
