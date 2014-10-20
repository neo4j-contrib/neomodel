========================
Hooks and Django signals
========================

You may define the following hook methods on your `StructuredNode` sub classes::

    pre_save, post_save, pre_delete, post_delete, post_create

An example of the post creation hook::

    class Person(StructuredNode):

        def post_create(self):
            email_welcome_message(self)
            super(Person, self).post_create()

Note there currently is no support for hooking relationship disconnect / connect.

Django signals
==============

Signals are also supported providing django is available::

    from django.db.models import signals
    signals.post_save.connect(your_func, sender=Person)
