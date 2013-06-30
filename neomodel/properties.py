from neomodel.exception import InflateError, DeflateError
from datetime import datetime, date
import time
import pytz
import json
import sys
import functools

if sys.version_info >= (3, 0):
    unicode = lambda x: str(x)


def validator(fn):
    fn_name = fn.func_name if hasattr(fn, 'func_name') else fn.__name__
    if fn_name == 'inflate':
        exc_class = InflateError
    elif fn_name == 'deflate':
        exc_class = DeflateError
    else:
        raise Exception("Unknown Property method " + fn_name)

    @functools.wraps(fn)
    def validator(self, value, node_id=None):
        try:
            return fn(self, value)
        except Exception as e:
            raise exc_class(self.name, self.owner, str(e), node_id)
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


class IntegerProperty(Property):
    @validator
    def inflate(self, value):
        return int(value)

    @validator
    def deflate(self, value):
        return int(value)


class FloatProperty(Property):
    @validator
    def inflate(self, value):
        return float(value)

    @validator
    def deflate(self, value):
        return float(value)


class BooleanProperty(Property):
    @validator
    def inflate(self, value):
        return bool(value)

    @validator
    def deflate(self, value):
        return bool(value)


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
            epoch = int(value)
        except ValueError:
            raise ValueError('integer expected, got {0} cant inflate to datetime'.format(value))
        return datetime.utcfromtimestamp(epoch).replace(tzinfo=pytz.utc)

    @validator
    def deflate(self, value):
        if not isinstance(value, datetime):
            raise ValueError('datetime object expected, got {0}'.format(value))
        return time.mktime(value.utctimetuple())


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

    def __get__(self, node, cls):
        return getattr(node, self.aliased_to()) if node else self

    def __set__(self, node, value):
        setattr(node, self.aliased_to(), value)

    @property
    def index(self):
        return getattr(self.owner, self.aliased_to()).index

    @property
    def unique_index(self):
        return getattr(self.owner, self.aliased_to()).unique_index
