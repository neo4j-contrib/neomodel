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

When defining classes that require a custom ``__init__(self, ...)`` constructor,
the `super()` class constructor must also be called **always**.

This is a ``neomodel`` design convention that must be followed very strictly or risk breaking the whole process of
instantiating a model with data retrieved from the database.

For example, suppose a scenario where it should be possible for an ``Item`` entity to also be instantiated via
a ``Product`` entity. One way to achieve this, would be to have ``Item``'s constructor accept a ``product`` parameter:
 ::

    class Item(StructuredNode):
        name = StringProperty(unique_index=True)
        uid = StringProperty(unique_index=True)

        def __init__(self, product=None, *args, **kwargs):
            if product is not None:
                self.product = product
                kwargs["uid"] = 'g.' + str(self.product.pk)
                kwargs["name"] = self.product.product_name
            super(Item, self).__init__(*args, **kwargs)

Note here that it is impossible to automatically infer that ``product`` is a parameter that is only used in the
derivation of ``Item``'s attributes and the objective is to preserve the ability to instantiate ``Item`` both via a
``product`` **and** simply via keyword arguments.

A more elegant way to provide the same functionality here would be to leave ``Item``'s constructor as is and provide an
additional function (e.g. ``from_product()``) for the alternative means of initialising the entity.

The first way of achieving this functionality and involves optional variables is probably easier to handle in Python 3
onwards (due to less restrictions in handling positional and keyword arguments) while the second way that involves
setting up a separate function might be more preferable in earlier versions of Python.

It is also important to note that `StructuredNode`'s constructor will override properties set
(which are defined on the class). Therefore constructor parameters must be passed via `kwargs` (as above).
These can also be set after calling the constructor but this would skip validation.

.. _automatic_class_resolution:

Automatic class resolution
--------------------------
Neomodel is able to transform nodes to native data model objects, automatically, via a *node-class registry*
that is progressively built up during the definition of the models.

This *registry* is a dictionary that provides a mapping from the set of labels associated with a node to the class
that is implied by this set of labels.

Consider for example the following snippet of code::

    import neomodel


    class BasePerson(neomodel.StructuredNode):
        pass


    class TechnicalPerson(BasePerson):
        pass


    class PilotPerson(BasePerson):
        pass

Once this script is executed, the *node-class registry* would contain the following entries: ::

    {"BasePerson"}                    --> class BasePerson
    {"BasePerson", "TechnicalPerson"} --> class TechnicalPerson
    {"BasePerson", "PilotPerson"}     --> class PilotPerson

Therefore, a ``Node`` with labels ``"BasePerson", "TechnicalPerson"`` would lead to the instantiation of a
``TechnicalPerson`` object. This automatic resolution is **optional** and can be invoked automatically via
``neomodel.Database.cypher_query`` if its ``resolve_objects`` parameter is set to ``True`` (the default is ``False``).

This automatic class resolution however, requires a bit of caution:

1. As a consequence of the way the *node-class registry* is built up and used, if a query results in instantiating an
   object whose class definition has not yet been imported, then exception
   ``neomodel.exceptions.ModelDefinitionMismatch`` will be raised.
        * Given the above class hierarchy, suppose that each of the classes ``BasePerson``, ``TechnicalPerson``,
          ``PilotPerson`` were defined in separate files / modules and a script only included::

              from base_models import BasePerson
              from pilot_models import PilotPerson

          Then, this would mean that the ``BasePerson, TechnicalPerson --> TechnicalPerson`` entry would not have been
          created in the node-class registry and therefore it would be impossible to resolve any `Node` objects (if
          they happened to come up in a query) to an application specific object.

2. Since the only way to resolve objects at runtime is this mapping of a set of labels to a class, then
   this mapping **must** be guaranteed to be unique. Therefore, if for any reason a class gets **redefined**, then
   exception ``neomodel.exceptions.ClassAlreadyDefined`` will be raised.
        * Given the above class hierarchy, suppose that an attempt was made to redefine one of the existing classes in
          the local scope of some function ::

                import neomodel

                class BasePerson(neomodel.StructuredNode):
                    pass


                class TechnicalPerson(BasePerson):
                    pass


                class PilotPerson(BasePerson):
                    pass


                def some_function():
                    class PilotPerson(BasePerson):
                        pass

          If this was left unchecked and once ``some_function()`` executes, it would replace the mapping of
          ``{"BasePerson", "PilotPerson"}`` to ``PilotPerson`` **in the global scope** with a mapping of the same
          set of labels but towards the class defined within the **local scope** of ``some_function``.

Both ``ModelDefinitionMismatch`` and ``ClassAlreadyDefined`` produce an error message that returns the labels of the
node that created the problem (either the `Node` returned from the database or the class that was attempted to be
redefined) as well as the state of the current *node-class registry*. These two pieces of information can be used to
debug the model mismatch further.


``neomodel`` under multiple processes and threads
-------------------------------------------------
It is very important to realise that neomodel preserves a mapping of the set of labels associated with the Neo4J
Data Base Management System (DBMS) Node to the Python class this node corresponds to within a class hierarchy.
Detailed information about this is available in :ref:`automatic_class_resolution`.

This mapping is preserved **within the same process** along with **transaction information**.

Once a script that uses neomodel starts up, it imports its model definitions and starts communicating with the
database within its own process.

* neomodel internally creates a new `session <https://neo4j.com/docs/driver-manual/1.7/sessions-transactions/>`_
  and through that session creates any additional transactions if required.
* neomodel internally creates and updates a node-class registry.
* Any additional threads spun up from this process will re-use the node-class registry.
* Multiple calls to transaction handling functions will re-use a transaction if one is already going on **within the
  same thread**.
    * Separate threads can start different transactions but all of these transactions will be executed within the
      same session.

A script can still use neomodel across more than one processes as long as it gets re-initialised within each process
to the desired state. That is, once a new process starts, the ``neomodel.db`` object will be re-initialised and the new
process would have to import any application specific models it requires for its operation. As the two processes are
independent, they will start different *sessions* to the Neo4j DBMS.

Any transactions occurring within the same session will take care of constraints and indices without any special care.
However, transactions across different sessions are *not aware of each other* and therefore can lead to database
exceptions.

For example, if an entity is declared with a unique index on one of its properties and two threads spun up from the
same process attempt a ``get_or_create``, then one of them will ``create`` the node and the other will ``get`` it.
No exceptions will be raised and ``get_or_create`` would have proceeded as expected. However, if the exact same scenario
was attempted over transactions in two completely different sessions, then ``get_or_create`` would appear to have
proceeded as expected in both of them, but one of them would further receive an exception about violating the uniqueness
constraint (which is not exactly what is expected when a ``get_or_create`` is executed).

Both of these conditions: Multiple threads spun from a single process and multiple processes spun from a main process,
are very relevant to the operation of neomodel over
`Neo4J Clusters <https://neo4j.com/docs/operations-manual/current/clustering/>`_ and the way tests might be invoked.

A high throughput cluster environment (a few CORE clusters surrounded by many READ_REPLICAs) can use neomodel with
``bolt+routing:`` over *multiple threads* to issue parallel read queries (over explicitly declared READ transactions).
The same however would not work for parallel WRITE transactions because they all get processed within the
same session and there is no performance gain. In that case, the only solution would be to use neomodel over
*multiple processes* but ensure beforehand that any operations will not create conflicts (or anticipate and resolve
gracefully the exceptions that might be raised).

Similar considerations should also be given when writing tests for specific test modes. For example, ``pytest``
collects tests within a directory and launches them in their own context and ``pytest-xdist`` and ``pytest-forked``
can run tests in a distributed / parallel mode. Exactly the same considerations regarding initialising / re-initialising
neomodel apply here as well and at the very minimum, you should ensure that tests either re-use classes, wherever
possible, or do not re-use the same class names within the same context of execution.

