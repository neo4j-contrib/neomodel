from _typeshed import Incomplete
from typing import Any

__all__ = ['AttemptedCardinalityViolation', 'CardinalityViolation', 'ConstraintValidationFailed', 'DeflateConflict', 'DeflateError', 'DoesNotExist', 'InflateConflict', 'InflateError', 'MultipleNodesReturned', 'NeomodelException', 'NotConnected', 'RequiredProperty', 'UniqueProperty', 'NodeClassNotDefined', 'NodeClassAlreadyDefined', 'RelationshipClassNotDefined', 'RelationshipClassRedefined', 'FeatureNotSupported']

class NeomodelException(Exception): ...
class AttemptedCardinalityViolation(NeomodelException): ...

class CardinalityViolation(NeomodelException):
    rel_manager: Incomplete
    actual: Incomplete
    def __init__(self, rel_manager: Any, actual: int | str) -> None: ...

class ModelDefinitionException(NeomodelException):
    db_node_rel_class: Incomplete
    current_node_class_registry: Incomplete
    current_db_specific_node_class_registry: Incomplete
    def __init__(self, db_node_rel_class: Any, current_node_class_registry: dict[frozenset, Any], current_db_specific_node_class_registry: dict[str, dict]) -> None: ...

class NodeClassNotDefined(ModelDefinitionException): ...
class RelationshipClassNotDefined(ModelDefinitionException): ...

class RelationshipClassRedefined(ModelDefinitionException):
    remapping_to_class: Incomplete
    def __init__(self, db_rel_class_type: Any, current_node_class_registry: dict[frozenset, Any], current_db_specific_node_class_registry: dict[str, dict], remapping_to_class: Any) -> None: ...

class NodeClassAlreadyDefined(ModelDefinitionException): ...

class ConstraintValidationFailed(ValueError, NeomodelException):
    message: Incomplete
    def __init__(self, msg: str) -> None: ...

class DeflateError(ValueError, NeomodelException):
    property_name: Incomplete
    node_class: Incomplete
    msg: Incomplete
    obj: Incomplete
    def __init__(self, key: str, cls: Any, msg: str, obj: Any) -> None: ...

class DoesNotExist(NeomodelException):
    message: str
    def __init__(self, msg: str) -> None: ...
    def __reduce__(self) -> tuple: ...

class InflateConflict(NeomodelException):
    cls_name: Incomplete
    property_name: Incomplete
    value: Incomplete
    nid: Incomplete
    def __init__(self, cls: Any, key: str, value: Any, nid: str) -> None: ...

class InflateError(ValueError, NeomodelException):
    property_name: Incomplete
    node_class: Incomplete
    msg: Incomplete
    obj: Incomplete
    def __init__(self, key: str, cls: Any, msg: str, obj: Any | None = None) -> None: ...

class DeflateConflict(InflateConflict):
    cls_name: Incomplete
    property_name: Incomplete
    value: Incomplete
    nid: Incomplete
    def __init__(self, cls: Any, key: str, value: Any, nid: str) -> None: ...

class MultipleNodesReturned(ValueError, NeomodelException):
    message: Incomplete
    def __init__(self, msg: str) -> None: ...

class NotConnected(NeomodelException):
    action: Incomplete
    node1: Incomplete
    node2: Incomplete
    def __init__(self, action: str, node1: Any, node2: Any) -> None: ...

class RequiredProperty(NeomodelException):
    property_name: Incomplete
    node_class: Incomplete
    def __init__(self, key: str, cls: Any) -> None: ...

class UniqueProperty(ConstraintValidationFailed):
    message: Incomplete
    def __init__(self, msg: str) -> None: ...

class FeatureNotSupported(NeomodelException):
    message: Incomplete
    def __init__(self, msg: str) -> None: ...
