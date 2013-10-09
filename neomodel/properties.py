from .exception import InflateError, DeflateError, RequiredProperty, NoSuchProperty
from datetime import datetime, date
from .relationship_manager import RelationshipDefinition, RelationshipManager
import os
import types
import pytz
import json
import sys
import functools
import logging
logger = logging.getLogger(__name__)

if sys.version_info >= (3, 0):
    unicode = lambda x: str(x)


class PropertyManager(object):
    """Common stuff for handling properties in nodes and relationships"""
    def __init__(self, *args, **kwargs):
        for key, val in self._class_properties().items():
            if val.__class__ is RelationshipDefinition:
                self.__dict__[key] = val.build_manager(self, key)
            # handle default values
            elif isinstance(val, (Property,)) and not isinstance(val, (AliasProperty,)):
                if not key in kwargs or kwargs[key] is None:
                    if val.has_default:
                        kwargs[key] = val.default_value()
        for key, value in kwargs.items():
            if not(key.startswith("__") and key.endswith("__")):
                setattr(self, key, value)

    @property
    def __properties__(self):
        node_props = {}
        for key, value in self.__dict__.items():
            if not (key.startswith('_') or value is None
                    or isinstance(value,
                        (types.MethodType, RelationshipManager, AliasProperty,))):
                node_props[key] = value
        return node_props

    @classmethod
    def deflate(cls, obj_props, obj=None):
        """ deflate dict ready to be stored """
        deflated = {}
        for key, prop in cls._class_properties().items():
            if (not isinstance(prop, AliasProperty)
                    and issubclass(prop.__class__, Property)):
                if key in obj_props and obj_props[key] is not None:
                    deflated[key] = prop.deflate(obj_props[key], obj)
                elif prop.has_default:
                    deflated[key] = prop.deflate(prop.default_value(), obj)
                elif prop.required:
                    raise RequiredProperty(key, cls)
        return deflated

    @classmethod
    def get_property(cls, name):
        try:
            neo_property = getattr(cls, name)
        except AttributeError:
            raise NoSuchProperty(name, cls)
        if not issubclass(neo_property.__class__, Property)\
                or not issubclass(neo_property.__class__, AliasProperty):
            NoSuchProperty(name, cls)
        return neo_property

    @classmethod
    def _class_properties(cls):
        # get all dict values for inherited classes
        # reverse is done to keep inheritance order
        props = {}
        for scls in reversed(cls.mro()):
            for key, value in scls.__dict__.items():
                props[key] = value
        return props


def validator(fn):
    fn_name = fn.func_name if hasattr(fn, 'func_name') else fn.__name__
    if fn_name == 'inflate':
        exc_class = InflateError
    elif fn_name == 'deflate':
        exc_class = DeflateError
    else:
        raise Exception("Unknown Property method " + fn_name)

    @functools.wraps(fn)
    def validator(self, value, obj=None):
        try:
            return fn(self, value)
        except Exception as e:
            raise exc_class(self.name, self.owner, str(e), obj)
    return validator


class Property(object):
    def __init__(self, unique_index=False, index=False, required=False, default=None):
        if default and required:
            raise Exception("required and default are mutually exclusive")

        if unique_index and index:
            raise Exception("unique_index and index are mutually exclusive")

        self.required = required
        self.unique_index = unique_index
        self.index = index
        self.default = default
        self.has_default = True if self.default is not None else False

    def default_value(self):
        if self.has_default:
            if hasattr(self.default, '__call__'):
                return self.default()
            else:
                return self.default
        else:
            raise Exception("No default value specified")

    @property
    def is_indexed(self):
        return self.unique_index or self.index


class StringProperty(Property):
    @validator
    def inflate(self, value):
        return unicode(value)

    @validator
    def deflate(self, value):
        return unicode(value)

    def default_value(self):
        return unicode(super(StringProperty, self).default_value())


class IntegerProperty(Property):
    @validator
    def inflate(self, value):
        return int(value)

    @validator
    def deflate(self, value):
        return int(value)

    def default_value(self):
        return int(super(IntegerProperty, self).default_value())


class FloatProperty(Property):
    @validator
    def inflate(self, value):
        return float(value)

    @validator
    def deflate(self, value):
        return float(value)

    def default_value(self):
        return float(super(FloatProperty, self).default_value())


class BooleanProperty(Property):
    @validator
    def inflate(self, value):
        return bool(value)

    @validator
    def deflate(self, value):
        return bool(value)

    def default_value(self):
        return bool(super(BooleanProperty, self).default_value())


class DateProperty(Property):
    @validator
    def inflate(self, value):
        return datetime.strptime(unicode(value), "%Y-%m-%d").date()

    @validator
    def deflate(self, value):
        if not isinstance(value, date):
            msg = 'datetime.date object expected, got {0}'.format(repr(value))
            raise ValueError(msg)
        return value.isoformat()


class DateTimeProperty(Property):
    @validator
    def inflate(self, value):
        try:
            epoch = float(value)
        except ValueError:
            raise ValueError('float or integer expected, got {0} cant inflate to datetime'.format(value))
        return datetime.utcfromtimestamp(epoch).replace(tzinfo=pytz.utc)

    @validator
    def deflate(self, value):
        #: Fixed timestamp strftime following suggestion from
        # http://stackoverflow.com/questions/11743019/convert-python-datetime-to-epoch-with-strftime
        if not isinstance(value, datetime):
            raise ValueError('datetime object expected, got {0}'.format(value))
        if value.tzinfo:
            value = value.astimezone(pytz.utc)
            epoch_date = datetime(1970,1,1,tzinfo=pytz.utc)
        elif os.environ.get('NEOMODEL_FORCE_TIMEZONE', False):
            raise ValueError("Error deflating {} no timezone provided".format(value))
        else:
            logger.warning("No timezone sepecified on datetime object.. will be inflated to UTC")
            epoch_date = datetime(1970,1,1)
        return float((value - epoch_date).total_seconds())


class JSONProperty(Property):
    @validator
    def inflate(self, value):
        return json.loads(value)

    @validator
    def deflate(self, value):
        return json.dumps(value)


class AliasProperty(property, Property):
    def __init__(self, to=None):
        self.target = to
        self.required = False
        self.has_default = False

    def aliased_to(self):
        return self.target

    def __get__(self, obj, cls):
        return getattr(obj, self.aliased_to()) if obj else self

    def __set__(self, obj, value):
        setattr(obj, self.aliased_to(), value)

    @property
    def index(self):
        return getattr(self.owner, self.aliased_to()).index

    @property
    def unique_index(self):
        return getattr(self.owner, self.aliased_to()).unique_index
