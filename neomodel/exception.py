import importlib


class ConstraintValidationFailed(ValueError):
    def __init__(self, msg):
        self.message = msg


class UniqueProperty(ConstraintValidationFailed):
    def __init__(self, msg):
        self.message = msg


class DoesNotExist(Exception):
    def __init__(self, msg):
        self.message = msg
        Exception.__init__(self, msg)

    def __reduce__(self):
        return _get_correct_dne_obj, (self.__module__, self.message)


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


class InflateError(ValueError):
    def __init__(self, key, cls, msg, obj=None):
        self.property_name = key
        self.node_class = cls
        self.msg = msg
        self.obj = repr(obj)

    def __str__(self):
        return "Attempting to inflate property '{0}' on {1} of class '{2}': {3}".format(
            self.property_name, self.obj, self.node_class.__name__, self.msg)


class DeflateError(ValueError):
    def __init__(self, key, cls, msg, obj):
        self.property_name = key
        self.node_class = cls
        self.msg = msg
        self.obj = repr(obj)

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
            self.node1.id, self.node1.__class__.__name__,
            self.node2.id, self.node2.__class__.__name__)
        return msg


def _get_correct_dne_obj(cls, message):
    app_label, class_name = cls.rsplit(".", 1)
    neo_app = importlib.import_module(app_label)
    neo_object = getattr(neo_app, class_name)
    return neo_object.DoesNotExist(message)
