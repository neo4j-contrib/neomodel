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


Caveats
-------

It is very important to realise that `neomodel` builds an internal mapping of the set of labels associated with a node
to the Python class this node is supposed to be serialised to. This mapping is preserved **within the same process**.

This means that class names within a data model **must** be unique at least within the same process.

The following simple example illustrates exactly the sort of problematic condition this might create::

    import neomodel

    # Once the following class gets defined, `neomodel` will create a mapping between the set of
    # its labels and the class itself. Here, `Person` does not descend from any other class and therefore
    # the mapping will be {"Person"}->class Person
    class Person(neomodel.StructuredNode):
        uid = neomodel.UniqueIdProperty()
        full_name = neomodel.StringProperty()

    def some_function():
        # Class Person is local to `some_function`. This is perfectly valid Python
        # but its definition would reset the existing `neomodel` mapping of
        # {"Person"}->class Person, to {"Person"}->some_function.class Person
        class Person(neomodel.StructuredNode):
            uid = neomodel.UniqueIdProperty()
            age = neomodel.IntegerProperty()

        pass

    if __name__ == "__main__":
        Person(full_name="Tex Murhpy").save()
        some_function()
        Person(full_name="Donald Byrd").save()


This is disallowed in `neomodel` and an attempt to define a class whose labels are exactly the same as a class that has
already been defined will lead to raising exception `ClassAlreadyDefined`.
