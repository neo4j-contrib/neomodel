from neomodel import (StructuredNode, StringProperty)
from nose.plugins.skip import SkipTest
try:
    from django.conf import settings
    settings.configure()
    from neomodel.contrib.signals import SignalsMixin
    from django.db.models import signals
except ImportError as e:
    raise SkipTest("Couldn't import django signals skipping")


class TestSignals(StructuredNode, SignalsMixin):
    name = StringProperty()


SENT_SIGNAL = {}


def pre_save(sender, instance, signal):
    SENT_SIGNAL['pre_save'] = True
signals.pre_save.connect(pre_save, sender=TestSignals)


def post_save(sender, instance, signal):
    SENT_SIGNAL['post_save'] = True
signals.post_save.connect(post_save, sender=TestSignals)


def pre_delete(sender, instance, signal):
    SENT_SIGNAL['pre_delete'] = True
signals.pre_delete.connect(pre_delete, sender=TestSignals)


def post_delete(sender, instance, signal):
    SENT_SIGNAL['post_delete'] = True
signals.post_delete.connect(post_delete, sender=TestSignals)


def test_signals():
    test = TestSignals(name=1).save()
    assert 'post_save' in SENT_SIGNAL
    assert 'pre_save' in SENT_SIGNAL

    test.delete()
    assert 'post_delete' in SENT_SIGNAL
    assert 'pre_delete' in SENT_SIGNAL
