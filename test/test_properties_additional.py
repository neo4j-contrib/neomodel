"""
Additional tests for neomodel.properties module to improve coverage.
"""

import pytest

from neomodel.properties import (
    FulltextIndex,
    Property,
    StringProperty,
    VectorIndex,
    validator,
)


def test_validator_decorator_invalid_function():
    """Test validator decorator with invalid function name."""

    def invalid_function():
        pass

    # This should raise a ValueError because the function name is not "inflate" or "deflate"
    with pytest.raises(ValueError, match="Unknown Property method"):
        validator(invalid_function)


def test_validator_decorator_inflate_error():
    """Test validator decorator with inflate function that raises an exception."""

    class TestProperty(Property):
        def inflate(self, value, rethrow=False):
            raise ValueError("Test error")

        def deflate(self, value, rethrow=False):
            return value

    # Apply validator to inflate method
    TestProperty.inflate = validator(TestProperty.inflate)

    prop = TestProperty()
    prop.name = "test"
    prop.owner = "TestClass"

    with pytest.raises(Exception):  # Should raise InflateError
        prop.inflate("test_value")


def test_validator_decorator_deflate_error():
    """Test validator decorator with deflate function that raises an exception."""

    class TestProperty(Property):
        def inflate(self, value, rethrow=False):
            return value

        def deflate(self, value, rethrow=False):
            raise ValueError("Test error")

    # Apply validator to deflate method
    TestProperty.deflate = validator(TestProperty.deflate)

    prop = TestProperty()
    prop.name = "test"
    prop.owner = "TestClass"

    with pytest.raises(Exception):  # Should raise DeflateError
        prop.deflate("test_value")


def test_fulltext_index_initialization():
    """Test FulltextIndex initialization."""
    fti = FulltextIndex()
    assert fti.analyzer == "standard-no-stop-words"
    assert fti.eventually_consistent is False


def test_fulltext_index_initialization_with_params():
    """Test FulltextIndex initialization with parameters."""
    fti = FulltextIndex(analyzer="english", eventually_consistent=True)
    assert fti.analyzer == "english"
    assert fti.eventually_consistent is True


def test_vector_index_initialization():
    """Test VectorIndex initialization."""
    vi = VectorIndex()
    assert vi.dimensions == 1536
    assert vi.similarity_function == "cosine"


def test_vector_index_initialization_with_params():
    """Test VectorIndex initialization with custom parameters."""
    vi = VectorIndex(dimensions=512, similarity_function="euclidean")
    assert vi.dimensions == 512
    assert vi.similarity_function == "euclidean"


def test_property_initialization_mutually_exclusive_required_default():
    """Test Property initialization with mutually exclusive required and default."""
    with pytest.raises(ValueError, match="mutually exclusive"):
        StringProperty(required=True, default="test")


def test_property_initialization_mutually_exclusive_unique_index_index():
    """Test Property initialization with mutually exclusive unique_index and index."""
    with pytest.raises(ValueError, match="mutually exclusive"):
        StringProperty(unique_index=True, index=True)


def test_property_default_value_callable():
    """Test Property default_value with callable default."""

    def get_default():
        return "callable_default"

    prop = StringProperty(default=get_default)
    assert prop.default_value() == "callable_default"


def test_property_default_value_non_callable():
    """Test Property default_value with non-callable default."""
    prop = StringProperty(default="static_default")
    assert prop.default_value() == "static_default"


def test_property_default_value_no_default():
    """Test Property default_value with no default."""
    prop = StringProperty()
    with pytest.raises(ValueError, match="No default value specified"):
        prop.default_value()


def test_property_get_db_property_name():
    """Test Property get_db_property_name method."""
    prop = StringProperty(db_property="db_name")
    assert prop.get_db_property_name("attribute_name") == "db_name"

    prop_no_db = StringProperty()
    assert prop_no_db.get_db_property_name("attribute_name") == "attribute_name"


def test_property_is_indexed():
    """Test Property is_indexed property."""
    prop_indexed = StringProperty(index=True)
    assert prop_indexed.is_indexed is True

    prop_unique = StringProperty(unique_index=True)
    assert prop_unique.is_indexed is True

    prop_not_indexed = StringProperty()
    assert prop_not_indexed.is_indexed is False


def test_property_initialization_with_all_params():
    """Test Property initialization with all parameters."""
    fti = FulltextIndex()
    vi = VectorIndex()

    prop = StringProperty(
        name="test_prop",
        owner="TestClass",
        unique_index=True,
        index=False,
        fulltext_index=fti,
        vector_index=vi,
        required=True,
        default=None,
        db_property="db_prop",
        label="Test Label",
        help_text="Test help",
    )

    assert prop.name == "test_prop"
    assert prop.owner == "TestClass"
    assert prop.unique_index is True
    assert prop.index is False
    assert prop.fulltext_index is fti
    assert prop.vector_index is vi
    assert prop.required is True
    assert prop.default is None
    assert prop.db_property == "db_prop"
    assert prop.label == "Test Label"
    assert prop.help_text == "Test help"


def test_property_initialization_with_kwargs():
    """Test Property initialization with additional kwargs."""
    prop = StringProperty(custom_param="custom_value", another_param=123)
    assert hasattr(prop, "custom_param")
    assert hasattr(prop, "another_param")
    assert getattr(prop, "custom_param") == "custom_value"
    assert getattr(prop, "another_param") == 123


def test_property_has_default():
    """Test Property has_default property."""
    prop_with_default = StringProperty(default="test")
    assert prop_with_default.has_default is True

    prop_without_default = StringProperty()
    assert prop_without_default.has_default is False


def test_property_initialization_edge_cases():
    """Test Property initialization with edge cases."""
    # Test with empty string default
    prop = StringProperty(default="")
    assert prop.has_default is True
    assert prop.default_value() == ""

    # Test with None default
    prop = StringProperty(default=None)
    assert prop.has_default is False
    with pytest.raises(ValueError, match="No default value specified"):
        prop.default_value()


def test_property_initialization_with_indexes():
    """Test Property initialization with various index configurations."""
    # Test with only index
    prop = StringProperty(index=True)
    assert prop.index is True
    assert prop.unique_index is False
    assert prop.is_indexed is True

    # Test with only unique_index
    prop = StringProperty(unique_index=True)
    assert prop.unique_index is True
    assert prop.index is False
    assert prop.is_indexed is True

    # Test with neither
    prop = StringProperty()
    assert prop.index is False
    assert prop.unique_index is False
    assert prop.is_indexed is False


def test_property_initialization_with_required():
    """Test Property initialization with required parameter."""
    # Test with required=True
    prop = StringProperty(required=True)
    assert prop.required is True

    # Test with required=False
    prop = StringProperty(required=False)
    assert prop.required is False

    # Test default required value
    prop = StringProperty()
    assert prop.required is False


def test_property_initialization_with_fulltext_index():
    """Test Property initialization with fulltext_index."""
    fti = FulltextIndex(analyzer="test_analyzer")
    prop = StringProperty(fulltext_index=fti)
    assert prop.fulltext_index is fti


def test_property_initialization_with_vector_index():
    """Test Property initialization with vector_index."""
    vi = VectorIndex(dimensions=256)
    prop = StringProperty(vector_index=vi)
    assert prop.vector_index is vi


def test_property_initialization_with_db_property():
    """Test Property initialization with db_property."""
    prop = StringProperty(db_property="custom_db_name")
    assert prop.db_property == "custom_db_name"
    assert prop.get_db_property_name("attribute_name") == "custom_db_name"


def test_property_initialization_with_label_and_help_text():
    """Test Property initialization with label and help_text."""
    prop = StringProperty(label="Test Label", help_text="Test help text")
    assert prop.label == "Test Label"
    assert prop.help_text == "Test help text"
