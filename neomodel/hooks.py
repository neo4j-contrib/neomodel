from functools import wraps
from typing import Any, Callable


def _exec_hook(hook_name: str, self: Any) -> None:
    if hasattr(self, hook_name):
        getattr(self, hook_name)()


def hooks(fn: Callable) -> Callable:
    @wraps(fn)
    def hooked(self: Any) -> Callable:
        fn_name = getattr(fn, "func_name", fn.__name__)
        _exec_hook("pre_" + fn_name, self)
        val = fn(self)
        _exec_hook("post_" + fn_name, self)
        return val

    return hooked
