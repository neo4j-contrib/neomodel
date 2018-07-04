import importlib


class NeomodelException(Exception):
    """
    A base class that identifies all exceptions raised by :mod:`neomodel`.
    """


class AttemptedCardinalityViolation(NeomodelException):
    """
    Attempted to alter the database state against the cardinality definitions.

    Example: a relationship of type `One` trying to connect a second node.
    """
    pass


class CardinalityViolation(NeomodelException):
    """
    The state of database doesn't match the nodes cardinality definition.

    For example a relationship type `OneOrMore` returns no nodes.
    """
    def __init__(self, rel_manager, actual):
        self.rel_manager = str(rel_manager)
        self.actual = str(actual)

    def __str__(self):
        return "CardinalityViolation: Expected: {0}, got: {1}."\
            .format(self.rel_manager, self.actual)


class ConstraintValidationFailed(ValueError, NeomodelException):
    def __init__(self, msg):
        self.message = msg


class DeflateError(ValueError, NeomodelException):
    def __init__(self, key, cls, msg, obj):
        self.property_name = key
        self.node_class = cls
        self.msg = msg
        self.obj = repr(obj)

    def __str__(self):
        return ("Attempting to deflate property '{0}' on {1} of class '{2}': "
                "{3}".format(self.property_name, self.obj,
                             self.node_class.__name__, self.msg))


class DoesNotExist(NeomodelException):
    _model_class = None
    """
    This class property refers the model class that a subclass of this class
    belongs to. It is set by :class:`~neomodel.core.NodeMeta`.
    """

    def __init__(self, msg):
        if self._model_class is None:
            raise RuntimeError("This class hasn't been setup properly.")
        self.message = msg
        super(DoesNotExist, self).__init__(self, msg)

    def __reduce__(self):
        return _unpickle_does_not_exist, (self._model_class, self.message)


def _unpickle_does_not_exist(_model_class, message):
    return _model_class.DoesNotExist(message)


class InflateConflict(NeomodelException):
    def __init__(self, cls, key, value, nid):
        self.cls_name = cls.__name__
        self.property_name = key
        self.value = value
        self.nid = nid

    def __str__(self):
        return """Found conflict with node {0}, has property '{1}' with value '{2}'
            although class {3} already has a property '{1}'""".format(
            self.nid, self.property_name, self.value, self.cls_name)


class InflateError(ValueError, NeomodelException):
    def __init__(self, key, cls, msg, obj=None):
        self.property_name = key
        self.node_class = cls
        self.msg = msg
        self.obj = repr(obj)

    def __str__(self):
        return ("Attempting to inflate property '{0}' on {1} of class '{2}': "
                "{3}".format(self.property_name, self.obj,
                             self.node_class.__name__, self.msg))


class DeflateConflict(InflateConflict):
    def __init__(self, cls, key, value, nid):
        self.cls_name = cls.__name__
        self.property_name = key
        self.value = value
        self.nid = nid if nid else '(unsaved)'

    def __str__(self):
        return """Found trying to set property '{1}' with value '{2}' on node {0}
            although class {3} already has a property '{1}'""".format(
            self.nid, self.property_name, self.value, self.cls_name)


class MultipleNodesReturned(ValueError, NeomodelException):
    def __init__(self, msg):
        self.message = msg


class NotConnected(NeomodelException):
    def __init__(self, action, node1, node2):
        self.action = action
        self.node1 = node1
        self.node2 = node2

    def __str__(self):
        return ("Error performing '{0}' - Node {1} of type '{2}' is not "
                "connected to {2} of type '{3}'."
                .format(self.action, self.node1.id,
                        self.node1.__class__.__name__, self.node2.id,
                        self.node2.__class__.__name__))


class RequiredProperty(NeomodelException):
    def __init__(self, key, cls):
        self.property_name = key
        self.node_class = cls

    def __str__(self):
        return "property '{0}' on objects of class {1}".format(
            self.property_name, self.node_class.__name__)


class UniqueProperty(ConstraintValidationFailed):
    def __init__(self, msg):
        self.message = msg


__all__ = (
    AttemptedCardinalityViolation.__name__,
    CardinalityViolation.__name__,
    ConstraintValidationFailed.__name__,
    DeflateConflict.__name__,
    DeflateError.__name__,
    DoesNotExist.__name__,
    InflateConflict.__name__,
    InflateError.__name__,
    MultipleNodesReturned.__name__,
    NeomodelException.__name__,
    NotConnected.__name__,
    RequiredProperty.__name__,
    UniqueProperty.__name__
)
