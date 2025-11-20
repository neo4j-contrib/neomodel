"""
Simple tests for neomodel.util module to improve coverage.
"""

import inspect
import unittest
import warnings
from types import FrameType

from neomodel.util import (
    RelationshipDirection,
    _UnsavedNode,
    classproperty,
    deprecated,
    enumerate_traceback,
    get_graph_entity_properties,
    version_tag_to_integer,
)


class TestUtil(unittest.TestCase):
    """Test cases for neomodel.util module."""

    def test_relationship_direction_enum(self):
        """Test RelationshipDirection enum values."""
        self.assertEqual(RelationshipDirection.OUTGOING, 1)
        self.assertEqual(RelationshipDirection.INCOMING, -1)
        self.assertEqual(RelationshipDirection.EITHER, 0)

    def test_deprecated_decorator(self):
        """Test the deprecated decorator functionality."""

        @deprecated("This function is deprecated")
        def deprecated_function():
            return "test"

        # Test that the function still works
        self.assertEqual(deprecated_function(), "test")

        # Test that a deprecation warning is issued
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            deprecated_function()
            self.assertEqual(len(w), 1)
            self.assertTrue(issubclass(w[0].category, DeprecationWarning))
            self.assertIn("This function is deprecated", str(w[0].message))

    def test_classproperty(self):
        """Test classproperty decorator."""

        class TestClass:
            _value = "test"

            @classproperty
            def value(cls):
                return cls._value

        self.assertEqual(TestClass.value, "test")

        # Test that it works on instances too
        instance = TestClass()
        self.assertEqual(instance.value, "test")

    def test_unsaved_node(self):
        """Test _UnsavedNode class."""
        node = _UnsavedNode()
        self.assertEqual(repr(node), "<unsaved node>")
        self.assertEqual(str(node), "<unsaved node>")

    def test_get_graph_entity_properties(self):
        """Test get_graph_entity_properties function."""

        # Mock entity with properties
        class MockEntity:
            def __init__(self):
                self._properties = {"name": "test", "age": 25}

        entity = MockEntity()
        properties = get_graph_entity_properties(entity)
        self.assertEqual(properties, {"name": "test", "age": 25})

    def test_enumerate_traceback(self):
        """Test enumerate_traceback function."""

        def test_function():
            current_frame = inspect.currentframe()
            return list(enumerate_traceback(current_frame))

        result = test_function()
        self.assertGreater(len(result), 0)
        self.assertTrue(
            all(isinstance(item, tuple) and len(item) == 2 for item in result)
        )
        self.assertTrue(all(isinstance(depth, int) for depth, frame in result))
        self.assertTrue(all(isinstance(frame, FrameType) for depth, frame in result))

    def test_version_tag_to_integer(self):
        """Test version_tag_to_integer function."""
        # Test basic version conversion
        self.assertEqual(version_tag_to_integer("5.4.0"), 50400)
        self.assertEqual(version_tag_to_integer("4.0.0"), 40000)
        self.assertEqual(version_tag_to_integer("3.2.1"), 30201)

        # Test with less than 3 components
        self.assertEqual(version_tag_to_integer("5.4"), 50400)
        self.assertEqual(version_tag_to_integer("5"), 50000)

        # Test with aura suffix
        self.assertEqual(version_tag_to_integer("5.14-aura"), 51400)
        self.assertEqual(version_tag_to_integer("4.0-aura"), 40000)

        # Test edge cases
        self.assertEqual(version_tag_to_integer("0.0.0"), 0)
        self.assertEqual(version_tag_to_integer("1.0.0"), 10000)

    def test_version_tag_to_integer_invalid_input(self):
        """Test version_tag_to_integer with invalid input."""
        with self.assertRaises(ValueError):
            version_tag_to_integer("invalid")

        with self.assertRaises(ValueError):
            version_tag_to_integer("5.4.invalid")

        with self.assertRaises(ValueError):
            version_tag_to_integer("")


if __name__ == "__main__":
    unittest.main()
