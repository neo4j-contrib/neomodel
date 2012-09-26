class Property(object):
    def __init__(self, unique_index=False, index=False, optional=False):
        self.optional = optional
        if unique_index and index:
            raise Exception("unique_index and index are mutually exclusive")
        self.unique_index = unique_index
        self.index = index

    @property
    def is_indexed(self):
        return self.unique_index or self.index


class StringProperty(Property):
    def validate(self, value):
        if value == None and self.optional:
            return True
        if isinstance(value, (str, unicode)):
            return True
        else:
            raise TypeError("Object of type str expected got " + str(value))


class IntegerProperty(Property):
    def validate(self, value):
        if value == None and self.optional:
            return True
        if isinstance(value, (int, long)):
            return True
        else:
            raise TypeError("Object of type int or long expected")


class FloatProperty(Property):
    def validate(self, value):
        if value == None and self.optional:
            return True
        if isinstance(value, (float)):
            return True
        else:
            raise TypeError("Object of type int or long expected")


class BoolProperty(Property):
    def validate(self, value):
        if value == None and self.optional:
            return True
        if isinstance(value, (int, long)):
            return True
        else:
            raise TypeError("Object of type int or long expected")
