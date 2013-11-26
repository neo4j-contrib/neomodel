class UniqueProperty(ValueError):
    def __init__(self, key, value, index, node='(unsaved)'):
        self.property_name = key
        self.value = value
        self.index_name = index
        self.node = node

    def __str__(self):
        msg = "Value '{0}' of property {1} of node {2} in index {3} is not unique"
        return msg.format(self.value, self.property_name, self.node, self.index_name)


class DataInconsistencyError(ValueError):
    def __init__(self, key, value, index, node='(unsaved)'):
        self.property_name = key
        self.value = value
        self.index_name = index
        self.node = node

    def __str__(self):
        return """DATA INCONSISTENCY ERROR - PLEASE READ.

        Setting value '{0}' for unique property '{1}' in index '{2}' for node {3} failed!

        Neo4j servers before version 1.9.M03 do not support unique index
        enforcement via ?unique=create_or_fail:
        http://docs.neo4j.org/chunked/1.9.M03/rest-api-unique-indexes.html
        Due to this, neomodel checks indexes for uniqueness conflicts prior to
        executing a batch which then updates the node's properties and the index.

        Here lies a race condition that your code has hit, the index value has
        probably been taken in between checking for conflicts and executing the batch,
        the properties in neo4j for node {3} don't match those in the index '{2}'.

        You must resolve this manually. To find the node currently indexed under the given
        key, value pair run the following cypher query:

        START a=node:{2}({1}="{0}") RETURN a;
        """.format(self.value, self.property_name, self.index_name, str(self.node))


class DoesNotExist(Exception):
    pass


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


class NoSuchProperty(Exception):
    def __init__(self, key, cls):
        self.property_name = key
        self.node_class = cls

    def __str__(self):
        return "No property '{0}' on object of class '{1}'".format(
            self.property_name, self.node_class.__name__)


class PropertyNotIndexed(Exception):
    pass


class NotConnected(Exception):
    def __init__(self, action, node1, node2):
        self.action = action
        self.node1 = node1
        self.node2 = node2

    def __str__(self):
        msg = "Error preforming '{0}' - ".format(self.action)
        msg += "Node {0} of type '{1}' is not connected to {2} of type '{3}'".format(
            self.node1.__node__._id, self.node1.__class__.__name__,
            self.node2.__node__._id, self.node2.__class__.__name__)
        return msg
