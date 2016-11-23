import os
from . import config

signals = None
try:
    if not 'DJANGO_SETTINGS_MODULE' in os.environ:
        from django.conf import settings
        settings.configure()
    from django.db.models import signals
    SIGNAL_SUPPORT = True
except ImportError:
    SIGNAL_SUPPORT = False


def exec_hook(hook_name, self, *args, **kwargs):
    if hasattr(self, hook_name):
        getattr(self, hook_name)(*args, **kwargs)

    if config.DJANGO_SIGNALS and signals and hasattr(signals, hook_name):
        sig = getattr(signals, hook_name)
        sig.send(sender=self.__class__, instance=self)



def hooks(fn):
    def hooked(self, *args, **kwargs):
        fn_name = fn.func_name if hasattr(fn, 'func_name') else fn.__name__
        exec_hook('pre_' + fn_name, self, *args, **kwargs)
        val = fn(self, *args, **kwargs)
        exec_hook('post_' + fn_name, self, *args, **kwargs)
        return val
    return hooked
