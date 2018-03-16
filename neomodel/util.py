import logging
import warnings
from functools import wraps


logger = logging.getLogger(__name__)


def classproperty(f):
    class cpf:
        def __init__(self, getter):
            self.getter = getter

        def __get__(self, obj, type=None):
            return self.getter(type)

    return cpf(f)


def deprecated(message):
    """
    A wrapper to mark functions and methods as deprecated. Uses of such will
    emit the provided ``message``.
    """
    def messaging_decorator(f):
        @wraps(f)
        def function_wrapper(*args, **kwargs):
            warnings.warn(message, category=DeprecationWarning, stacklevel=2)
            return f(*args, **kwargs)
        return function_wrapper

    return messaging_decorator


def display_for(key):
    def display_choice(self):
        return getattr(self.__class__, key).choices[getattr(self, key)]
    return display_choice


# Just used for error messages
class _UnsavedNode:
    def __repr__(self):
        return '<unsaved node>'

    def __str__(self):
        return self.__repr__()
