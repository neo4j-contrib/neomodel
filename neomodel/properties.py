from neomodel.exception import InflateError, DeflateError
from datetime import datetime, date
import time
import pytz


def validator(fn):
    if fn.func_name is 'inflate':
        exc_class = InflateError
    elif fn.func_name == 'deflate':
        exc_class = DeflateError
    else:
        raise Exception("Unknown Property method " + fn.func_name)

    def validator(self, value):
        try:
            return fn(self, value)
        except Exception as e:
            raise exc_class(self.name, self.owner, e.message)
    return validator


class Property(object):
    def __init__(self, unique_index=False, index=False, required=False):
        self.required = required
        if unique_index and index:
            raise Exception("unique_index and index are mutually exclusive")
        self.unique_index = unique_index
        self.index = index

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
            msg = 'datetime.date object expected, got {}'.format(repr(value))
            raise ValueError(msg)
        return value.isoformat()


class DateTimeProperty(Property):
    @validator
    def inflate(self, value):
        try:
            epoch = int(value)
        except ValueError:
            raise ValueError('integer expected, got {} cant inflate to datetime'.format(value))
        return datetime.utcfromtimestamp(epoch).replace(tzinfo=pytz.utc)

    @validator
    def deflate(self, value):
        if not isinstance(value, datetime):
            raise ValueError('datetime object expected, got {}'.format(value))
        if not value.tzinfo:
            raise ValueError('datetime object {} must have a timezone'.format(value))
        return time.mktime(value.utctimetuple())
