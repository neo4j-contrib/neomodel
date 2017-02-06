def _exec_hook(hook_name, self):
    if hasattr(self, hook_name):
        getattr(self, hook_name)()


def hooks(fn):
    def hooked(self):
        fn_name = fn.func_name if hasattr(fn, 'func_name') else fn.__name__
        _exec_hook('pre_' + fn_name, self)
        val = fn(self)
        _exec_hook('post_' + fn_name, self)
        return val
    return hooked
