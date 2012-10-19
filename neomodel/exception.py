class NotUnique(Exception):
    pass


class DoesNotExist(Exception):
    pass


class RequiredProperty(Exception):
    pass


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


class ReadOnlyError(Exception):
    pass


class NoSuchProperty(Exception):
    pass


class PropertyNotIndexed(Exception):
    pass
