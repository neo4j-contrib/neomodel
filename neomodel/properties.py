from neomodel.exception import InflateError, DeflateError


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
        except ValueError as e:
            if hasattr(e, 'message') and e.message:
                message = e.message
            else:
                message = str(e)
            raise exc_class(self.name, self.owner, message)
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
