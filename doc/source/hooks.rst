=====
Hooks
=====

The following hook methods can be defined on `StructuredNode` sub classes::

    pre_save, post_save, pre_delete, post_delete, post_create

All these hook methods do not accept any arguments. An example of the post creation hook is as follows::

    class Person(StructuredNode):

        def post_create(self):
            email_welcome_message(self)

Note that the `post_create` hook is not called by the `get_or_create` and `create_or_update` methods.

Save hooks are called regardless of wether the node is new or not.
To determine if a node exists in `pre_save`, check for an `id` attribute on self.

Hooks on relationships
----------------------

The hook methods `pre_save` and `post_save` are available on `StructuredRel` models.
They are executed when calling save on the object directly or when creating a new relationship via `connect`.

Note that in the `pre_save` call during a `connect` the start and end nodes are not available.

Django signals
==============

Signals are now supported through the django_neomodel_ module.

.. _django_neomodel: https://github.com/neo4j-contrib/django-neomodel
