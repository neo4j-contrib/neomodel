# attempt to import hook handler from django_neomodel
try:
    from django_neomodel import signal_exec_hook as exec_hook
except ImportError:
    def exec_hook(hook_name, self, *args, **kwargs):
        if hasattr(self, hook_name):
            getattr(self, hook_name)(*args, **kwargs)


def hooks(fn):
    def hooked(self, *args, **kwargs):
        fn_name = fn.func_name if hasattr(fn, 'func_name') else fn.__name__
        exec_hook('pre_' + fn_name, self, *args, **kwargs)
        val = fn(self, *args, **kwargs)
        exec_hook('post_' + fn_name, self, *args, **kwargs)
        return val
    return hooked
