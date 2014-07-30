class UniqueProperty(ValueError):
    def __init__(self, msg):
        self.message = msg


class DoesNotExist(Exception):
    def __init__(self, msg):
        self.message = msg


class MultipleNodesReturned(ValueError):
    def __init__(self, msg):
        self.message = msg


class RequiredProperty(Exception):
    def __init__(self, key, cls):
        self.property_name = key
        self.node_class = cls

    def __str__(self):
        return "property '{0}' on objects of class {1}".format(
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


class TransactionError(Exception):
    def __init__(self, message, jexception, java_trace, id):
        self.java_exception = jexception
        self.id = id
        self.message = message
        self.java_trace = java_trace

    def __str__(self):
        trace = "\n    ".join(self.java_trace)

        return "\nException: {0}\n Transaction ID {1}\nTrace: {2}\n".format(
                self.java_exception, self.id, self.message, trace)


def _obj_to_str(obj):
    if obj is None:
        return "object"
    if obj.__class__.__name__ == 'Node':
        return "node ({0})".format(obj._id)
    else:
        return "relationship ({0})".format(obj._id)


class InflateError(ValueError):
    def __init__(self, key, cls, msg, obj=None):
        self.property_name = key
        self.node_class = cls
        self.msg = msg
        self.obj = _obj_to_str(obj)

    def __str__(self):
        return "Attempting to inflate property '{0}' on {1} of class '{2}': {3}".format(
            self.property_name, self.obj, self.node_class.__name__, self.msg)


class DeflateError(ValueError):
    def __init__(self, key, cls, msg, obj):
        self.property_name = key
        self.node_class = cls
        self.msg = msg
        self.obj = _obj_to_str(obj)

    def __str__(self):
        return "Attempting to deflate property '{0}' on {1} of class '{2}': {3}".format(
            self.property_name, self.obj, self.node_class.__name__, self.msg)


class NotConnected(Exception):
    def __init__(self, action, node1, node2):
        self.action = action
        self.node1 = node1
        self.node2 = node2

    def __str__(self):
        msg = "Error performing '{0}' - ".format(self.action)
        msg += "Node {0} of type '{1}' is not connected to {2} of type '{3}'".format(
            self.node1._id, self.node1.__class__.__name__,
            self.node2._id, self.node2.__class__.__name__)
        return msg
