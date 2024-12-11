from typing import Any, Optional, Type, Union


class NeomodelException(Exception):
    """
    A base class that identifies all exceptions raised by :mod:`neomodel`.
    """

    pass


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

    def __init__(self, rel_manager: Any, actual: Union[int, str]):
        self.rel_manager = str(rel_manager)
        self.actual = str(actual)

    def __str__(self) -> str:
        return (
            f"CardinalityViolation: Expected: {self.rel_manager}, got: {self.actual}."
        )


class ModelDefinitionException(NeomodelException):
    """
    Abstract exception to handle error conditions related to the node-to-class registry.
    """

    def __init__(
        self,
        db_node_rel_class: Any,
        current_node_class_registry: dict[frozenset, Any],
        current_db_specific_node_class_registry: dict[str, dict],
    ):
        """
        Initialises the exception with the database node that caused the missmatch.

        :param db_node_rel_class: Depending on the concrete class, this is either a Neo4j driver node object
               from the DBMS, or a data model class from an application's hierarchy.
        :param current_node_class_registry: Dictionary that maps frozenset of
               node labels to model classes
        :param current_db_specific_node_class_registry: Dictionary that maps frozenset of
                node labels to model classes for specific databases
        """
        self.db_node_rel_class = db_node_rel_class
        self.current_node_class_registry = current_node_class_registry
        self.current_db_specific_node_class_registry = (
            current_db_specific_node_class_registry
        )

    def _get_node_class_registry_formatted(self) -> str:
        """
        Returns the current node class registry string formatted as a list of
        Labels --> <class to instantiate> entries.

        :return: str
        """
        output = "\n".join(
            map(
                lambda x: f"{','.join(x[0])} --> {x[1]}",
                self.current_node_class_registry.items(),
            )
        )
        for db, db_registry in self.current_db_specific_node_class_registry.items():
            output += f"\n\nDatabase-specific: {db}\n"
            output += "\n".join(
                list(
                    map(
                        lambda x: f"{','.join(x[0])} --> {x[1]}",
                        db_registry.items(),
                    )
                )
            )
        return output


class NodeClassNotDefined(ModelDefinitionException):
    """
    Raised when it is impossible to resolve a Neo4j driver Node to a
    data model object. This can happen as a result of a query returning
    nodes for which class definitions do exist but have not been imported
    or because the retrieved nodes contain more labels for a known class.

    In either of these cases the mismatch must be reported
    """

    def __str__(self) -> str:
        node_labels = ",".join(self.db_node_rel_class.labels)

        return f"Node with labels {node_labels} does not resolve to any of the known objects\n{self._get_node_class_registry_formatted()}\n"


class RelationshipClassNotDefined(ModelDefinitionException):
    """
    Raised when it is impossible to resolve a Neo4j driver Relationship to
    a data model object.
    """

    def __str__(self) -> str:
        relationship_type = self.db_node_rel_class.type
        return f"""
            Relationship of type {relationship_type} does not resolve to any of the known objects
            {self._get_node_class_registry_formatted()}
            Note that when using the fetch_relations method, the relationship type must be defined in the model, even if only defined to StructuredRel.
            Otherwise, neomodel will not be able to determine which relationship model to resolve into.
        """


class RelationshipClassRedefined(ModelDefinitionException):
    """
    Raised when an attempt is made to re-map a relationship label to a relationship model of an entirely different type
    """

    def __init__(
        self,
        db_rel_class_type: Any,
        current_node_class_registry: dict[frozenset, Any],
        current_db_specific_node_class_registry: dict[str, dict],
        remapping_to_class: Any,
    ):
        """
        Initialises a relationship redefinition exception with the required data as follows:

        :param db_rel_class_type: The type of the relationship that caused the error.
        :type db_rel_class_type: str (The label of the relationship that caused the error)
        :param current_node_class_registry: The current db object's node-class registry.
        :param current_db_specific_node_class_registry: The current db object's node-class registry for specific databases.
        :type current_node_class_registry: dict
        :param remapping_to_class: The relationship class the relationship type was attempted to be redefined to.
        :type remapping_to_class: class
        """
        super().__init__(
            db_rel_class_type,
            current_node_class_registry,
            current_db_specific_node_class_registry,
        )
        self.remapping_to_class = remapping_to_class

    def __str__(self) -> str:
        relationship_type = self.db_node_rel_class
        return f"Relationship of type {relationship_type} redefined as {self.remapping_to_class}.\n{self._get_node_class_registry_formatted()}\n"


class NodeClassAlreadyDefined(ModelDefinitionException):
    """
    Raised when an attempt is made to re-map a set of labels to a class
    that already has a mapping within the node-to-class registry.
    """

    def __str__(self) -> str:
        node_class_labels = ",".join(self.db_node_rel_class.inherited_labels())

        return f"Class {self.db_node_rel_class.__module__}.{self.db_node_rel_class.__name__} with labels {node_class_labels} already defined:\n{self._get_node_class_registry_formatted()}\n"


class ConstraintValidationFailed(ValueError, NeomodelException):
    def __init__(self, msg: str):
        self.message = msg


class DeflateError(ValueError, NeomodelException):
    def __init__(self, key: str, cls: Any, msg: str, obj: Any):
        self.property_name = key
        self.node_class = cls
        self.msg = msg
        self.obj = repr(obj)

    def __str__(self) -> str:
        return f"Attempting to deflate property '{self.property_name}' on {self.obj} of class '{self.node_class.__name__}': {self.msg}"


class DoesNotExist(NeomodelException):
    _model_class: Optional[Type] = None
    """
    This class property refers the model class that a subclass of this class
    belongs to. It is set by :class:`~neomodel.core.NodeMeta`.
    """

    def __init__(self, msg: str):
        if self._model_class is None:
            raise RuntimeError("This class hasn't been setup properly.")
        self.message: str = msg
        super().__init__(self, msg)

    def __reduce__(self) -> tuple:
        return _unpickle_does_not_exist, (self._model_class, self.message)


def _unpickle_does_not_exist(_model_class: Any, message: str) -> DoesNotExist:
    return _model_class.DoesNotExist(message)


class InflateConflict(NeomodelException):
    def __init__(self, cls: Any, key: str, value: Any, nid: str):
        self.cls_name = cls.__name__
        self.property_name = key
        self.value = value
        self.nid = nid

    def __str__(self) -> str:
        return f"Found conflict with node {self.nid}, has property '{self.property_name}' with value '{self.value}' although class {self.cls_name} already has a property '{self.property_name}'"


class InflateError(ValueError, NeomodelException):
    def __init__(self, key: str, cls: Any, msg: str, obj: Optional[Any] = None):
        self.property_name = key
        self.node_class = cls
        self.msg = msg
        self.obj = repr(obj)

    def __str__(self) -> str:
        return f"Attempting to inflate property '{self.property_name}' on {self.obj} of class '{self.node_class.__name__}': {self.msg}"


class DeflateConflict(InflateConflict):
    def __init__(self, cls: Any, key: str, value: Any, nid: str):
        self.cls_name = cls.__name__
        self.property_name = key
        self.value = value
        self.nid = nid if nid else "(unsaved)"

    def __str__(self) -> str:
        return f"Found trying to set property '{self.property_name}' with value '{self.value}' on node {self.nid} although class {self.cls_name} already has a property '{self.property_name}'"


class MultipleNodesReturned(ValueError, NeomodelException):
    def __init__(self, msg: str):
        self.message = msg


class NotConnected(NeomodelException):
    def __init__(self, action: str, node1: Any, node2: Any):
        self.action = action
        self.node1 = node1
        self.node2 = node2

    def __str__(self) -> str:
        return f"Error performing '{self.action}' - Node {self.node1.element_id} of type '{self.node1.__class__.__name__}' is not connected to {self.node2.element_id} of type '{self.node2.__class__.__name__}'."


class RequiredProperty(NeomodelException):
    def __init__(self, key: str, cls: Any):
        self.property_name = key
        self.node_class = cls

    def __str__(self) -> str:
        return f"property '{self.property_name}' on objects of class {self.node_class.__name__}"


class UniqueProperty(ConstraintValidationFailed):
    def __init__(self, msg: str):
        self.message = msg


class FeatureNotSupported(NeomodelException):
    def __init__(self, msg: str):
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
    UniqueProperty.__name__,
    NodeClassNotDefined.__name__,
    NodeClassAlreadyDefined.__name__,
    RelationshipClassNotDefined.__name__,
    RelationshipClassRedefined.__name__,
    FeatureNotSupported.__name__,
)
