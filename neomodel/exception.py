class UniqueProperty(ValueError):
    def __init__(self, request, index):
        self.property_name = request.body['key']
        self.value = request.body['value']
        self.index_name = index

    def __str__(self):
        return "Value '{0}' of property {1} in index {2} is not unique".format(
                self.value, self.property_name, self.index_name)


class DoesNotExist(Exception):
    pass


class RequiredProperty(Exception):
    def __init__(self, key, cls):
        self.property_name = key
        self.node_class = cls

    def __str__(self):
        return "property {0} on objects of class {1}".format(
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
        return "\n{0}: {1}\nQuery: {2}\nParams: {3}\nTrace: {4}\n".format(
            self.java_exception, self.message, self.query, repr(self.query_parameters), trace)


class InflateError(ValueError):
    def __init__(self, key, cls, msg):
        self.property_name = key
        self.node_class = cls
        self.msg = msg

    def __str__(self):
        return "Attempting to inflate property '{0}' on object of class '{1}': {2}".format(
                self.property_name, self.node_class.__name__, self.msg)


class DeflateError(ValueError):
    def __init__(self, key, cls, msg):
        self.property_name = key
        self.node_class = cls
        self.msg = msg

    def __str__(self):
        return "Attempting to deflate property '{0}' on object of class '{1}': {2}".format(
                self.property_name, self.node_class.__name__, self.msg)


class ReadOnlyError(Exception):
    pass


class NoSuchProperty(Exception):
    def __init__(self, key, cls):
        self.property_name = key
        self.node_class = cls

    def __str__(self):
        return "No property '{0}' on object of class '{1}'".format(
                self.property_name, self.node_class.__name__)


class PropertyNotIndexed(Exception):
    pass
