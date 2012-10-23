from neomodel.exception import InflateError, DeflateError
from datetime import datetime
import time


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
        return str(value)

    @validator
    def deflate(self, value):
        return str(value)


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


class DatetimeProperty(Property):
    @validator
    # get property from database to obj
    def inflate(self, value):
        if not isinstance(value, (int, long, float)):
            raise ValueError('Not a number.')
        return datetime.utcfromtimestamp(value)

    @validator
    # save object to db
    def deflate(self, value):
        if not isinstance(value, datetime):
            raise ValueError('Not a datetime object.')
        if not value.tzinfo:
            raise Exception('Datetime object must be timezone aware.')
        return time.mktime(value.utctimetuple())
