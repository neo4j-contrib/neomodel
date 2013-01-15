class NoSignalsSupport(object):
    signals_support = False

import os

try:
    if not 'DJANGO_SETTINGS_MODULE' in os.environ:
        from django.conf import settings
        settings.configure()
    from django.db.models import signals
except ImportError:
    Signals = NoSignalsSupport
else:
    class SignalsSupport(object):
        """ Provide support for pre_save, post_save, pre_delete and post_delete django signals::

            def greeting(sender, instance, signal):
                print("Hello {0}!".format(instance.name))

            class Person(StructuredNode):
                name = StringProperty()

            signals.post_save.connect(greeting, sender=Person)
        """

        signals_support = True

        def pre_save(self):
            signals.pre_save.send(sender=self.__class__, instance=self)

        def post_save(self):
            signals.post_save.send(sender=self.__class__, instance=self)

        def pre_delete(self):
            signals.pre_delete.send(sender=self.__class__, instance=self)

        def post_delete(self):
            signals.post_delete.send(sender=self.__class__, instance=self)

    Signals = SignalsSupport
