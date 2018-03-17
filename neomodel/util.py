import logging
import warnings
from functools import wraps
from types import SimpleNamespace
from weakref import WeakSet


logger = logging.getLogger(__name__)


registries = SimpleNamespace(
    concrete_node_models=WeakSet()
)


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


def display_for(property_name):
    def display_choice(self):
        return getattr(self.__class__, property_name).choices[getattr(self, property_name)]
    return display_choice


def get_members_of_type(cls, wanted_type, unwanted_type=()):
    result = {}
    for baseclass in reversed(cls.__mro__):
        result.update({k: v for k, v in vars(baseclass).items()
                       if isinstance(v, wanted_type)
                       and not isinstance(v, unwanted_type)})
    return result


def is_abstract_node_model(cls):
    """
    Tests whether the provided class has the attribute ``__abstract_node__``
    and if it evaluates as ``True``.

    :rtype: :class:`bool`
    """
    if not '__abstract_node__' in cls.__dict__:
        return False
    return bool(cls.__abstract_node__)


# Just used for error messages
class _UnsavedNode:
    def __repr__(self):
        return '<unsaved node>'

    def __str__(self):
        return self.__repr__()
