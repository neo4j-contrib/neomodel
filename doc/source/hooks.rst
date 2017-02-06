=====
Hooks
=====

You may define the following hook methods on your `StructuredNode` sub classes::

    pre_save, post_save, pre_delete, post_delete, post_create

All take no arguments. An example of the post creation hook::

    class Person(StructuredNode):

        def post_create(self):
            email_welcome_message(self)

Note the `post_create` hook is not called by `get_or_create` and `create_or_update` methods.

Save hooks are called regardless of wether the node is new or not.
To determine if a node exists in `pre_save`, check for an `id` attribute on self.

Django signals
==============

Signals are now supported through the django_neomodel_ module.

.. _django_neomodel: https://github.com/robinedwards/django-neomodel
