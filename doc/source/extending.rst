==================
Extending neomodel
==================

Inheritance
-----------
Neomodel extends the ability to compose classes by inheritance to the backend. This 
makes it possible to create a node class which extends the functionality that neomodel provides
(such as `neomodel.contrib.SemiStructuredNode`).

Creating purely abstract classes is achieved using the `__abstract_node__` property on base classes::

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
Mixins can be used to share functionality between nodes classes::

    class UserMixin(object):
        name = StringProperty(unique_index=True)
        password = StringProperty()

    class CreditMixin(object):
        balance = IntegerProperty(index=True)

        def credit_account(self, amount):
            self.balance = self.balance + int(amount)
            self.save()

    class Shopper(StructuredNode, UserMixin, CreditMixin):
        pass

    jim = Shopper(name='jimmy', balance=300).save()
    jim.credit_account(50)

Please note that it has to be ensured that the mixins *do not* inherit 
from `StructuredNode` but that the concrete class does.

Overriding the StructuredNode constructor
-----------------------------------------

When defining classes that have a custom `__init__(self, ...)` constructor,
the `super()` class constructor must also be called::

    class Item(StructuredNode):
        name = StringProperty(unique_index=True)
        uid = StringProperty(unique_index=True)

        def __init__(self, product, *args, **kwargs):
            self.product = product
            kwargs["uid"] = 'g.' + str(self.product.pk)
            kwargs["name"] = self.product.product_name

            super(Item, self).__init__(self, *args, **kwargs)

It is important to note that `StructuredNode`'s constructor will override properties set (which are defined on the class).
Therefore constructor parameters must be passed via `kwargs` (as above). 
These can also be set after calling the constructor but this would skip validation.
