"""
Additional tests for neomodel.exceptions module to improve coverage.
"""

import pytest

from neomodel import StructuredNode
from neomodel.exceptions import (
    AttemptedCardinalityViolation,
    CardinalityViolation,
    ConstraintValidationFailed,
    DeflateConflict,
    DeflateError,
    DoesNotExist,
    FeatureNotSupported,
    InflateConflict,
    InflateError,
    ModelDefinitionException,
    MultipleNodesReturned,
    NeomodelException,
    NotConnected,
    RequiredProperty,
    UniqueProperty,
)


def test_neomodel_exception():
    """Test NeomodelException base class."""
    exc = NeomodelException("Test message")
    assert str(exc) == "Test message"
    assert isinstance(exc, Exception)


def test_attempted_cardinality_violation():
    """Test AttemptedCardinalityViolation exception."""
    exc = AttemptedCardinalityViolation("Test message")
    assert str(exc) == "Test message"
    assert isinstance(exc, NeomodelException)


def test_cardinality_violation():
    """Test CardinalityViolation exception."""
    exc = CardinalityViolation("Test rel_manager", 5)
    assert exc.rel_manager == "Test rel_manager"
    assert exc.actual == "5"
    assert "Expected: Test rel_manager, got: 5" in str(exc)


def test_cardinality_violation_str():
    """Test CardinalityViolation string representation."""
    exc = CardinalityViolation("OneOrMore", 0)
    assert "Expected: OneOrMore, got: 0" in str(exc)


def test_model_definition_exception():
    """Test ModelDefinitionException initialization."""
    db_node = {"labels": ["TestNode"]}
    registry = {frozenset(["TestNode"]): "TestClass"}
    db_registry = {"test_db": {frozenset(["TestNode"]): "TestClass"}}

    exc = ModelDefinitionException(db_node, registry, db_registry)
    assert exc.db_node_rel_class is db_node
    assert exc.current_node_class_registry is registry
    assert exc.current_db_specific_node_class_registry is db_registry


def test_model_definition_exception_get_node_class_registry_formatted():
    """Test ModelDefinitionException _get_node_class_registry_formatted method."""
    db_node = {"labels": ["TestNode"]}
    registry = {frozenset(["TestNode"]): "TestClass"}
    db_registry = {"test_db": {frozenset(["TestNode"]): "TestClass"}}

    exc = ModelDefinitionException(db_node, registry, db_registry)
    formatted = exc._get_node_class_registry_formatted()  # type: ignore

    assert "TestNode --> TestClass" in formatted
    assert "Database-specific: test_db" in formatted


def test_constraint_validation_failed():
    """Test ConstraintValidationFailed exception."""
    exc = ConstraintValidationFailed("Test constraint error")
    assert str(exc) == "Test constraint error"
    assert isinstance(exc, NeomodelException)


def test_unique_property():
    """Test UniqueProperty exception."""
    exc = UniqueProperty("Test unique constraint error")
    assert exc.message == "Test unique constraint error"
    assert isinstance(exc, ConstraintValidationFailed)


def test_required_property():
    """Test RequiredProperty exception."""

    class TestClass:
        pass

    exc = RequiredProperty("test_prop", TestClass)
    assert exc.property_name == "test_prop"
    assert exc.node_class is TestClass
    assert "property 'test_prop' on objects of class TestClass" in str(exc)


def test_required_property_str():
    """Test RequiredProperty string representation."""

    class TestClass:
        pass

    exc = RequiredProperty("age", TestClass)
    assert "property 'age' on objects of class TestClass" in str(exc)


def test_inflate_error():
    """Test InflateError exception."""

    class TestClass:
        pass

    exc = InflateError("test_prop", TestClass, "Test inflate error", "test_obj")
    assert exc.property_name == "test_prop"
    assert exc.node_class is TestClass
    assert exc.msg == "Test inflate error"
    assert exc.obj == "'test_obj'"
    assert (
        "property 'test_prop' on 'test_obj' of class 'TestClass': Test inflate error"
        in str(exc)
    )


def test_inflate_error_str():
    """Test InflateError string representation."""

    class TestClass:
        pass

    exc = InflateError("name", TestClass, "Invalid value", None)
    assert "property 'name' on None of class 'TestClass': Invalid value" in str(exc)


def test_deflate_error():
    """Test DeflateError exception."""

    class TestClass:
        pass

    exc = DeflateError("test_prop", TestClass, "Test deflate error", "test_obj")
    assert exc.property_name == "test_prop"
    assert exc.node_class is TestClass
    assert exc.msg == "Test deflate error"
    assert exc.obj == "'test_obj'"
    assert (
        "property 'test_prop' on 'test_obj' of class 'TestClass': Test deflate error"
        in str(exc)
    )


def test_deflate_error_str():
    """Test DeflateError string representation."""

    class TestClass:
        pass

    exc = DeflateError("age", TestClass, "Invalid age", None)
    assert "property 'age' on None of class 'TestClass': Invalid age" in str(exc)


def test_inflate_conflict():
    """Test InflateConflict exception."""

    class TestClass:
        pass

    exc = InflateConflict(TestClass, "test_prop", "test_value", "test_nid")
    assert (
        str(exc)
        == "Found conflict with node test_nid, has property 'test_prop' with value 'test_value' although class TestClass already has a property 'test_prop'"
    )
    assert isinstance(exc, NeomodelException)


def test_deflate_conflict():
    """Test DeflateConflict exception."""

    class TestClass:
        pass

    exc = DeflateConflict(TestClass, "test_prop", "test_value", "test_nid")
    assert (
        str(exc)
        == "Found trying to set property 'test_prop' with value 'test_value' on node test_nid although class TestClass already has a property 'test_prop'"
    )
    assert isinstance(exc, NeomodelException)


def test_multiple_nodes_returned():
    """Test MultipleNodesReturned exception."""
    exc = MultipleNodesReturned("Test multiple nodes error")
    assert str(exc) == "Test multiple nodes error"
    assert isinstance(exc, NeomodelException)


def test_does_not_exist():
    """Test DoesNotExist exception."""

    class TestClass:
        pass

    # Set the model class
    DoesNotExist._model_class = TestClass

    exc = DoesNotExist("Test does not exist error")
    assert exc.message == "Test does not exist error"
    assert isinstance(exc, NeomodelException)


def test_does_not_exist_no_model_class():
    """Test DoesNotExist exception without model class."""
    # Reset the model class
    DoesNotExist._model_class = None

    with pytest.raises(RuntimeError, match="This class hasn't been setup properly"):
        DoesNotExist("Test error")


def test_not_connected():
    """Test NotConnected exception."""

    class MockNode1:
        def __init__(self, element_id):
            self.element_id = element_id

    class MockNode2:
        def __init__(self, element_id):
            self.element_id = element_id

    node1 = MockNode1("id1")
    node2 = MockNode2("id2")
    exc = NotConnected("connect", node1, node2)
    assert exc.action == "connect"
    assert exc.node1 is node1
    assert exc.node2 is node2
    assert (
        "Error performing 'connect' - Node id1 of type 'MockNode1' is not connected to id2 of type 'MockNode2'"
        in str(exc)
    )


def test_not_connected_str():
    """Test NotConnected string representation."""

    class MockNode1:
        def __init__(self, element_id):
            self.element_id = element_id

    class MockNode2:
        def __init__(self, element_id):
            self.element_id = element_id

    exc = NotConnected("delete", MockNode1("id1"), MockNode2("id2"))
    assert (
        "Error performing 'delete' - Node id1 of type 'MockNode1' is not connected to id2 of type 'MockNode2'"
        in str(exc)
    )


def test_feature_not_supported():
    """Test FeatureNotSupported exception."""
    exc = FeatureNotSupported("Test feature not supported")
    assert exc.message == "Test feature not supported"
    assert isinstance(exc, NeomodelException)


def test_feature_not_supported_str():
    """Test FeatureNotSupported string representation."""
    exc = FeatureNotSupported("Vector indexes not supported in this version")
    assert exc.message == "Vector indexes not supported in this version"


def test_exception_string_representations():
    """Test string representations of various exceptions."""
    # Test with different message types
    exc = NeomodelException("Simple message")
    assert str(exc) == "Simple message"

    exc = NeomodelException("")
    assert str(exc) == ""

    exc = NeomodelException(None)
    assert str(exc) == "None"


def test_cardinality_violation_with_different_types():
    """Test CardinalityViolation with different actual value types."""
    exc = CardinalityViolation("OneOrMore", "zero")
    assert exc.actual == "zero"
    assert "Expected: OneOrMore, got: zero" in str(exc)

    exc = CardinalityViolation("One", 1)
    assert exc.actual == "1"
    assert "Expected: One, got: 1" in str(exc)


def test_model_definition_exception_with_empty_registries():
    """Test ModelDefinitionException with empty registries."""
    db_node = {"labels": ["TestNode"]}
    registry = {}
    db_registry = {}

    exc = ModelDefinitionException(db_node, registry, db_registry)
    formatted = exc._get_node_class_registry_formatted()  # type: ignore
    assert formatted == ""


def test_model_definition_exception_with_multiple_entries():
    """Test ModelDefinitionException with multiple registry entries."""
    db_node = {"labels": ["TestNode"]}
    registry = {frozenset(["Node1"]): "Class1", frozenset(["Node2"]): "Class2"}
    db_registry = {
        "db1": {frozenset(["Node3"]): "Class3"},
        "db2": {frozenset(["Node4"]): "Class4"},
    }

    exc = ModelDefinitionException(db_node, registry, db_registry)
    formatted = exc._get_node_class_registry_formatted()  # type: ignore

    assert "Node1 --> Class1" in formatted
    assert "Node2 --> Class2" in formatted
    assert "Database-specific: db1" in formatted
    assert "Database-specific: db2" in formatted
    assert "Node3 --> Class3" in formatted
    assert "Node4 --> Class4" in formatted
