class UniqueProperty(ValueError):
    def __init__(self, request, index):
        self.property_name = request.body['key']
        self.value = request.body['value']
        self.index_name = index

    def __str__(self):
        return "Value '{}' of property {} in index {} is not unique".format(
                self.value, self.property_name, self.index_name)


class DoesNotExist(Exception):
    pass


class RequiredProperty(Exception):
    def __init__(self, key, cls):
        self.property_name = key
        self.node_class = cls

    def __str__(self):
        return "property {} on objects of class {}".format(
                self.property_name, self.node_class.__name__)


class CypherException(Exception):
    def __init__(self, query, params, message, jexception, trace):
        self.message = message
        self.java_exception = jexception
        self.java_trace = trace
        self.query = query
        self.query_parameters = params

    def __str__(self):
        trace = "\n    ".join(self.java_trace)
        return "\n{}: {}\nQuery: {}\nParams: {}\nTrace: {}\n".format(
            self.java_exception, self.message, self.query, repr(self.query_parameters), trace)


class InflateError(ValueError):
    def __init__(self, key, cls, msg):
        self.property_name = key
        self.node_class = cls
        self.msg = msg

    def __str__(self):
        return "Attempting to inflate property '{}' on object of class '{}': {}".format(
                self.property_name, self.node_class.__name__, self.msg)


class DeflateError(ValueError):
    def __init__(self, key, cls, msg):
        self.property_name = key
        self.node_class = cls
        self.msg = msg

    def __str__(self):
        return "Attempting to deflate property '{}' on object of class '{}': {}".format(
                self.property_name, self.node_class.__name__, self.msg)


class ReadOnlyError(Exception):
    pass


class NoSuchProperty(Exception):
    pass


class PropertyNotIndexed(Exception):
    pass
