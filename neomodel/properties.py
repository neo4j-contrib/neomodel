from neomodel.exception import InflateError, DeflateError
from datetime import datetime
from datetime import date
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
        value = unicode(value)
        return datetime.strptime(value, "%Y-%m-%d").date()

    @validator
    def deflate(self, value):
        if not isinstance(value, date):
            raise ValueError(
                'datetime.date object is required, found %s.' % type(value)
                )
        return value.isoformat()


class DatetimeProperty(Property):
    @validator
    # get property from database to obj
    def inflate(self, value):
        if not isinstance(value, (int, long, float)):
            raise ValueError(
                'number is required, found %s.' % type(value)
                )
        return datetime.utcfromtimestamp(value).replace(tzinfo=pytz.utc)

    @validator
    # save object to db
    def deflate(self, value):
        if not isinstance(value, datetime):
            raise ValueError('datetime.datetime object is required, found %s.' % type(value))
        if not value.tzinfo:
            raise Exception('Datetime object must be timezone aware.')
        return time.mktime(value.utctimetuple())
