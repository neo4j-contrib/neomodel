from django.db.models import signals


class SignalsMixin(object):
    """ Provide support for pre_save, post_save, pre_delete and post_delete django signals::

        def greeting(sender, instance, signal):
            print("Hello {0}!".format(instance.name))

        class Person(StructuredNode):
            name = StringProperty()

        signals.post_save.connect(greeting, sender=Person)
    """
    def pre_save(self):
        signals.pre_save.send(sender=self.__class__, instance=self)

    def post_save(self):
        signals.post_save.send(sender=self.__class__, instance=self)

    def pre_delete(self):
        signals.pre_delete.send(sender=self.__class__, instance=self)

    def post_delete(self):
        signals.post_delete.send(sender=self.__class__, instance=self)
