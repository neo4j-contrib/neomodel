"""
Tests for the modernized configuration system.

This module tests the new dataclass-based configuration system with validation
and environment variable support.
"""

import os
import warnings
from unittest.mock import patch

import pytest

from neomodel import NeomodelConfig, config, get_config, reset_config, set_config
from neomodel.config import clear_deprecation_warnings

# Type ignore for dynamic module attributes created by config module replacement
# pylint: disable=no-member


class TestNeomodelConfig:
    """Test the NeomodelConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config_obj = NeomodelConfig()

        assert config_obj.database_url == "bolt://neo4j:foobarbaz@localhost:7687"
        assert config_obj.force_timezone is False
        assert config_obj.soft_cardinality_check is False
        assert config_obj.cypher_debug is False
        assert config_obj.slow_queries == 0.0
        assert config_obj.connection_timeout == 30.0
        assert config_obj.max_connection_pool_size == 100

    def test_config_validation(self):
        """Test configuration validation."""
        # Test valid configuration
        config_obj = NeomodelConfig(
            database_url="bolt://test:test@localhost:7687", connection_timeout=60.0
        )
        assert config_obj.connection_timeout == 60.0

        # Test invalid configuration
        with pytest.raises(ValueError, match="connection_timeout must be positive"):
            NeomodelConfig(connection_timeout=-1)

        with pytest.raises(ValueError, match="Invalid database URL"):
            NeomodelConfig(database_url="invalid-url")

        # Test slow_queries validation
        with pytest.raises(ValueError, match="slow_queries must be non-negative"):
            NeomodelConfig(slow_queries=-1.0)

        # Test additional validation branches
        with pytest.raises(
            ValueError, match="connection_acquisition_timeout must be positive"
        ):
            NeomodelConfig(connection_acquisition_timeout=-1)

        with pytest.raises(
            ValueError, match="max_connection_lifetime must be positive"
        ):
            NeomodelConfig(max_connection_lifetime=-1)

        with pytest.raises(
            ValueError, match="max_connection_pool_size must be positive"
        ):
            NeomodelConfig(max_connection_pool_size=-1)

        with pytest.raises(
            ValueError, match="max_transaction_retry_time must be positive"
        ):
            NeomodelConfig(max_transaction_retry_time=-1)

        # Test database URL validation with invalid format
        with pytest.raises(ValueError, match="Invalid database URL format"):
            NeomodelConfig(database_url="invalid")

        # Test database URL validation with missing scheme
        with pytest.raises(ValueError, match="Invalid database URL format"):
            NeomodelConfig(database_url="localhost:7687")

        # Test database URL validation with missing netloc
        with pytest.raises(ValueError, match="Invalid database URL format"):
            NeomodelConfig(database_url="bolt://")

        # Test database URL validation with exception handling
        # Use a URL that will cause urlparse to raise an exception
        with pytest.raises(ValueError, match="Invalid database URL"):
            NeomodelConfig(database_url="bolt://[invalid")

    def test_from_env(self):
        """Test loading configuration from environment variables."""
        env_vars = {
            "NEOMODEL_DATABASE_URL": "bolt://env:test@localhost:7687",
            "NEOMODEL_FORCE_TIMEZONE": "true",
            "NEOMODEL_CONNECTION_TIMEOUT": "45.0",
            "NEOMODEL_MAX_CONNECTION_POOL_SIZE": "50",
            "NEOMODEL_CYPHER_DEBUG": "true",
            "NEOMODEL_SLOW_QUERIES": "1.5",
        }

        with patch.dict(os.environ, env_vars):
            config_obj = NeomodelConfig.from_env()

            assert config_obj.database_url == "bolt://env:test@localhost:7687"
            assert config_obj.force_timezone is True
            assert config_obj.connection_timeout == 45.0
            assert config_obj.max_connection_pool_size == 50
            assert config_obj.cypher_debug is True
            assert config_obj.slow_queries == 1.5

    def test_to_dict(self):
        """Test converting configuration to dictionary."""
        config_obj = NeomodelConfig(
            database_url="bolt://test:test@localhost:7687", force_timezone=True
        )

        config_dict = config_obj.to_dict()

        assert config_dict["database_url"] == "bolt://test:test@localhost:7687"
        assert config_dict["force_timezone"] is True
        assert "driver" not in config_dict  # Non-serializable values excluded

    def test_to_dict_excludes_non_serializable(self):
        """Test that to_dict excludes non-serializable values."""
        config_obj = NeomodelConfig()
        config_dict = config_obj.to_dict()

        # These should be excluded from serialization
        excluded_fields = ["driver", "resolver", "trusted_certificates"]
        for field in excluded_fields:
            assert field not in config_dict

        # These should be included
        included_fields = ["database_url", "force_timezone", "connection_timeout"]
        for field in included_fields:
            assert field in config_dict

    def test_update(self):
        """Test updating configuration values."""
        config_obj = NeomodelConfig()

        config_obj.update(
            database_url="bolt://updated:test@localhost:7687", force_timezone=True
        )

        assert config_obj.database_url == "bolt://updated:test@localhost:7687"
        assert config_obj.force_timezone is True

        # Test validation on update
        with pytest.raises(ValueError):
            config_obj.update(connection_timeout=-1)

    def test_update_with_unknown_option(self):
        """Test update method with unknown configuration option."""
        config_obj = NeomodelConfig()

        # This should trigger a warning but not fail
        with pytest.warns(
            UserWarning, match="Unknown configuration option: unknown_field"
        ):
            config_obj.update(unknown_field="value")

        # Original values should remain unchanged
        assert config_obj.database_url == "bolt://neo4j:foobarbaz@localhost:7687"

    def test_setattr_initialization(self):
        """Test __setattr__ method initialization logic."""
        # Test that _initialized is set correctly
        config_obj = NeomodelConfig()

        # First attribute set should mark as initialized
        config_obj.database_url = "bolt://test:test@localhost:7687"
        assert hasattr(config_obj, "_initialized")
        assert config_obj._initialized is True  # pylint: disable=protected-access

        # Setting _initialized itself should not trigger validation
        config_obj._initialized = False  # pylint: disable=protected-access
        assert config_obj._initialized is False  # pylint: disable=protected-access

    def test_setattr_validation_skip(self):
        """Test that validation is skipped during initialization."""
        # Create config without triggering validation during init
        config_obj = NeomodelConfig()

        # Should not raise validation error during attribute setting
        # because validation is skipped when _initialized is not set
        config_obj.connection_timeout = -1  # This should not raise immediately

        # But validation should occur when explicitly called
        with pytest.raises(ValueError):
            config_obj._validate_config()  # pylint: disable=protected-access


class TestBackwardCompatibility:
    """Test backward compatibility with existing config usage."""

    def test_module_level_access(self):
        """Test that module-level attributes work as before."""
        # Test reading values
        assert isinstance(config.DATABASE_URL, str)
        assert isinstance(config.FORCE_TIMEZONE, bool)
        assert isinstance(config.SOFT_CARDINALITY_CHECK, bool)
        assert isinstance(config.CYPHER_DEBUG, bool)  # type: ignore[attr-defined]
        assert isinstance(config.SLOW_QUERIES, float)  # type: ignore[attr-defined]

        # Test setting values
        original_url = config.DATABASE_URL
        config.DATABASE_URL = "bolt://test:test@localhost:7687"
        assert config.DATABASE_URL == "bolt://test:test@localhost:7687"

        # Restore original value
        config.DATABASE_URL = original_url

    def test_all_property_setters(self):
        """Test all property setters for backward compatibility."""
        # Test DRIVER setter
        original_driver = config.DRIVER
        config.DRIVER = None
        assert config.DRIVER is None
        config.DRIVER = original_driver

        # Test DATABASE_NAME setter
        original_name = config.DATABASE_NAME
        config.DATABASE_NAME = "test_db"
        assert config.DATABASE_NAME == "test_db"
        config.DATABASE_NAME = original_name

        # Test CONNECTION_ACQUISITION_TIMEOUT setter
        original_timeout = config.CONNECTION_ACQUISITION_TIMEOUT
        config.CONNECTION_ACQUISITION_TIMEOUT = 120.0
        assert config.CONNECTION_ACQUISITION_TIMEOUT == 120.0
        config.CONNECTION_ACQUISITION_TIMEOUT = original_timeout

        # Test MAX_CONNECTION_LIFETIME setter
        original_lifetime = config.MAX_CONNECTION_LIFETIME
        config.MAX_CONNECTION_LIFETIME = 7200
        assert config.MAX_CONNECTION_LIFETIME == 7200
        config.MAX_CONNECTION_LIFETIME = original_lifetime

        # Test MAX_TRANSACTION_RETRY_TIME setter
        original_retry = config.MAX_TRANSACTION_RETRY_TIME
        config.MAX_TRANSACTION_RETRY_TIME = 60.0
        assert config.MAX_TRANSACTION_RETRY_TIME == 60.0
        config.MAX_TRANSACTION_RETRY_TIME = original_retry

        # Test RESOLVER setter
        original_resolver = config.RESOLVER
        config.RESOLVER = None
        assert config.RESOLVER is None
        config.RESOLVER = original_resolver

        # Test TRUSTED_CERTIFICATES setter
        original_certs = config.TRUSTED_CERTIFICATES
        config.TRUSTED_CERTIFICATES = None
        assert config.TRUSTED_CERTIFICATES is None
        config.TRUSTED_CERTIFICATES = original_certs

        # Test USER_AGENT setter
        original_agent = config.USER_AGENT
        config.USER_AGENT = "custom-agent/2.0"
        assert config.USER_AGENT == "custom-agent/2.0"
        config.USER_AGENT = original_agent

        # Test ENCRYPTED setter
        original_encrypted = config.ENCRYPTED
        config.ENCRYPTED = True
        assert config.ENCRYPTED is True
        config.ENCRYPTED = original_encrypted

        # Test KEEP_ALIVE setter
        original_keep_alive = config.KEEP_ALIVE
        config.KEEP_ALIVE = False
        assert config.KEEP_ALIVE is False
        config.KEEP_ALIVE = original_keep_alive

        # Test CYPHER_DEBUG setter
        original_cypher_debug = config.CYPHER_DEBUG
        config.CYPHER_DEBUG = True
        assert config.CYPHER_DEBUG is True
        config.CYPHER_DEBUG = original_cypher_debug

        # Test SLOW_QUERIES setter
        original_slow_queries = config.SLOW_QUERIES
        config.SLOW_QUERIES = 5.0
        assert config.SLOW_QUERIES == 5.0
        config.SLOW_QUERIES = original_slow_queries

    def test_custom_driver_configuration(self):
        """Test configuration with a custom Neo4j driver."""
        from unittest.mock import Mock

        # Create a mock driver
        mock_driver = Mock()
        mock_driver.close = Mock()

        # Test setting driver via NeomodelConfig
        config_obj = NeomodelConfig(driver=mock_driver)
        assert config_obj.driver is mock_driver

        # Test setting driver via module-level attribute
        original_driver = config.DRIVER
        config.DRIVER = mock_driver
        assert config.DRIVER is mock_driver

        # Test that driver is accessible through the config
        current_config = get_config()
        assert current_config.driver is mock_driver

        # Test that driver is excluded from serialization
        config_dict = config_obj.to_dict()
        assert "driver" not in config_dict

        # Restore original driver
        config.DRIVER = original_driver

    def test_validation_on_set(self):
        """Test that validation occurs when setting module-level attributes."""
        with pytest.raises(ValueError, match="connection_timeout must be positive"):
            config.CONNECTION_TIMEOUT = -1

    def test_validation_revert_on_error(self):
        """Test that values are reverted when validation fails."""
        original_timeout = config.CONNECTION_TIMEOUT

        # This should fail and revert the value
        with pytest.raises(ValueError):
            config.CONNECTION_TIMEOUT = -1

        # Value should be reverted to original
        assert config.CONNECTION_TIMEOUT == original_timeout

    def test_validation_revert_multiple_attributes(self):
        """Test validation and revert for multiple attributes."""
        original_values = {
            "CONNECTION_TIMEOUT": config.CONNECTION_TIMEOUT,
            "MAX_CONNECTION_POOL_SIZE": config.MAX_CONNECTION_POOL_SIZE,
        }

        # Test that each invalid value is reverted
        with pytest.raises(ValueError):
            config.CONNECTION_TIMEOUT = -1

        assert config.CONNECTION_TIMEOUT == original_values["CONNECTION_TIMEOUT"]

        with pytest.raises(ValueError):
            config.MAX_CONNECTION_POOL_SIZE = -1

        assert (
            config.MAX_CONNECTION_POOL_SIZE
            == original_values["MAX_CONNECTION_POOL_SIZE"]
        )

    def test_unknown_config_warning(self):
        """Test warning for unknown configuration options."""
        with pytest.warns(UserWarning, match="Unknown configuration option"):
            config_obj = get_config()
            config_obj.update(unknown_option="value")


class TestGlobalConfigManagement:
    """Test global configuration management functions."""

    def test_get_set_config(self):
        """Test getting and setting global configuration."""
        # Get default config
        config_obj = get_config()
        assert isinstance(config_obj, NeomodelConfig)

        # Set custom config
        custom_config = NeomodelConfig(database_url="bolt://custom:test@localhost:7687")
        set_config(custom_config)

        assert get_config().database_url == "bolt://custom:test@localhost:7687"

    def test_reset_config(self):
        """Test resetting configuration to defaults."""
        # Set custom config
        custom_config = NeomodelConfig(database_url="bolt://custom:test@localhost:7687")
        set_config(custom_config)

        # Reset to defaults
        reset_config()

        # Should load from environment or use defaults
        config_obj = get_config()
        assert isinstance(config_obj, NeomodelConfig)

    def test_get_config_singleton(self):
        """Test that get_config returns the same instance."""
        config1 = get_config()
        config2 = get_config()
        assert config1 is config2

    def test_set_config_replaces_singleton(self):
        """Test that set_config replaces the global instance."""
        original_config = get_config()
        custom_config = NeomodelConfig(database_url="bolt://custom:test@localhost:7687")

        set_config(custom_config)
        assert get_config() is custom_config
        assert get_config() is not original_config


class TestEnvironmentVariableSupport:
    """Test environment variable support."""

    def test_env_var_loading(self):
        """Test loading configuration from environment variables."""
        env_vars = {
            "NEOMODEL_DATABASE_URL": "bolt://env:test@localhost:7687",
            "NEOMODEL_FORCE_TIMEZONE": "true",
            "NEOMODEL_SOFT_CARDINALITY_CHECK": "true",
            "NEOMODEL_CYPHER_DEBUG": "true",
            "NEOMODEL_SLOW_QUERIES": "2.0",
        }

        with patch.dict(os.environ, env_vars):
            reset_config()  # Force reload from environment

            assert config.DATABASE_URL == "bolt://env:test@localhost:7687"
            assert config.FORCE_TIMEZONE is True
            assert config.SOFT_CARDINALITY_CHECK is True
            assert config.CYPHER_DEBUG is True
            assert config.SLOW_QUERIES == 2.0

    def test_env_var_type_conversion(self):
        """Test type conversion for environment variables."""
        env_vars = {
            "NEOMODEL_CONNECTION_TIMEOUT": "60.0",
            "NEOMODEL_MAX_CONNECTION_POOL_SIZE": "200",
            "NEOMODEL_ENCRYPTED": "true",
            "NEOMODEL_KEEP_ALIVE": "false",
            "NEOMODEL_CYPHER_DEBUG": "false",
            "NEOMODEL_SLOW_QUERIES": "0.5",
        }

        with patch.dict(os.environ, env_vars):
            reset_config()

            assert config.CONNECTION_TIMEOUT == 60.0
            assert config.MAX_CONNECTION_POOL_SIZE == 200
            assert config.ENCRYPTED is True  # type: ignore[attr-defined]
            assert config.KEEP_ALIVE is False  # type: ignore[attr-defined]
            assert config.CYPHER_DEBUG is False  # type: ignore[attr-defined]
            assert config.SLOW_QUERIES == 0.5  # type: ignore[attr-defined]

    def test_env_var_boolean_conversion(self):
        """Test boolean environment variable conversion edge cases."""
        # Test various boolean representations
        boolean_tests = [
            ("true", True),
            ("1", True),
            ("yes", True),
            ("on", True),
            ("false", False),
            ("0", False),
            ("no", False),
            ("off", False),
            ("TRUE", True),  # Case insensitive
            ("FALSE", False),
        ]

        for env_value, expected in boolean_tests:
            env_vars = {
                "NEOMODEL_FORCE_TIMEZONE": env_value,
                "NEOMODEL_ENCRYPTED": env_value,
                "NEOMODEL_KEEP_ALIVE": env_value,
                "NEOMODEL_SOFT_CARDINALITY_CHECK": env_value,
                "NEOMODEL_CYPHER_DEBUG": env_value,
            }

            with patch.dict(os.environ, env_vars):
                reset_config()
                assert config.FORCE_TIMEZONE == expected
                assert config.ENCRYPTED == expected  # type: ignore[attr-defined]
                assert config.KEEP_ALIVE == expected  # type: ignore[attr-defined]
                assert config.SOFT_CARDINALITY_CHECK == expected
                assert config.CYPHER_DEBUG == expected  # type: ignore[attr-defined]

    def test_env_var_numeric_conversion(self):
        """Test numeric environment variable conversion."""
        env_vars = {
            "NEOMODEL_CONNECTION_TIMEOUT": "45.5",
            "NEOMODEL_MAX_CONNECTION_POOL_SIZE": "150",
            "NEOMODEL_MAX_CONNECTION_LIFETIME": "7200",
            "NEOMODEL_MAX_TRANSACTION_RETRY_TIME": "60.0",
            "NEOMODEL_SLOW_QUERIES": "2.5",
        }

        with patch.dict(os.environ, env_vars):
            reset_config()
            assert config.CONNECTION_TIMEOUT == 45.5
            assert config.MAX_CONNECTION_POOL_SIZE == 150
            assert config.MAX_CONNECTION_LIFETIME == 7200  # type: ignore[attr-defined]
            assert config.MAX_TRANSACTION_RETRY_TIME == 60.0  # type: ignore[attr-defined]
            assert config.SLOW_QUERIES == 2.5  # type: ignore[attr-defined]

    def test_env_var_string_conversion(self):
        """Test string environment variable handling."""
        env_vars = {
            "NEOMODEL_DATABASE_URL": "bolt://custom:password@localhost:7687",
            "NEOMODEL_DATABASE_NAME": "test_database",
            "NEOMODEL_USER_AGENT": "custom-agent/1.0",
        }

        with patch.dict(os.environ, env_vars):
            reset_config()
            assert config.DATABASE_URL == "bolt://custom:password@localhost:7687"
            assert config.DATABASE_NAME == "test_database"  # type: ignore[attr-defined]
            assert config.USER_AGENT == "custom-agent/1.0"  # type: ignore[attr-defined]

    def test_env_var_missing_fields(self):
        """Test that missing environment variables use defaults."""
        # Clear all neomodel environment variables
        env_vars = {}
        for key in list(os.environ.keys()):
            if key.startswith("NEOMODEL_"):
                env_vars[key] = None  # Remove from environment

        with patch.dict(os.environ, env_vars, clear=True):
            reset_config()
            # Should use default values
            assert config.DATABASE_URL == "bolt://neo4j:foobarbaz@localhost:7687"
            assert config.FORCE_TIMEZONE is False
            assert config.CONNECTION_TIMEOUT == 30.0
            assert config.MAX_CONNECTION_POOL_SIZE == 100


class TestIntegration:
    """Test integration with existing neomodel functionality."""

    def test_config_with_properties(self):
        """Test that configuration works with neomodel properties."""
        from datetime import datetime

        from neomodel.properties import DateTimeProperty

        # Test FORCE_TIMEZONE functionality
        prop = DateTimeProperty()

        # Default should not raise error
        config.FORCE_TIMEZONE = False
        result = prop.deflate(datetime.now())
        assert result is not None

        # With FORCE_TIMEZONE=True, should raise error for naive datetime
        config.FORCE_TIMEZONE = True
        with pytest.raises(Exception):  # May be ValueError or DeflateError
            prop.deflate(datetime.now())

        # Restore default
        config.FORCE_TIMEZONE = False

    def test_config_with_cardinality(self):
        """Test that configuration works with cardinality checking."""
        # Test SOFT_CARDINALITY_CHECK functionality
        original_value = config.SOFT_CARDINALITY_CHECK

        config.SOFT_CARDINALITY_CHECK = True
        assert config.SOFT_CARDINALITY_CHECK is True

        config.SOFT_CARDINALITY_CHECK = False
        assert config.SOFT_CARDINALITY_CHECK is False

        # Restore original value
        config.SOFT_CARDINALITY_CHECK = original_value


class TestDeprecationWarnings:
    """Test deprecation warnings for legacy configuration access."""

    def setup_method(self):
        """Clear deprecation warnings before each test."""
        clear_deprecation_warnings()

    def test_deprecation_warning_on_get(self):
        """Test that deprecation warnings are issued when accessing legacy attributes."""
        with pytest.warns(
            DeprecationWarning, match="Accessing config.DATABASE_URL is deprecated"
        ):
            _ = config.DATABASE_URL

        with pytest.warns(
            DeprecationWarning, match="Accessing config.FORCE_TIMEZONE is deprecated"
        ):
            _ = config.FORCE_TIMEZONE

        with pytest.warns(
            DeprecationWarning, match="Accessing config.CYPHER_DEBUG is deprecated"
        ):
            _ = config.CYPHER_DEBUG

    def test_deprecation_warning_on_set(self):
        """Test that deprecation warnings are issued when setting legacy attributes."""
        with pytest.warns(
            DeprecationWarning, match="Setting config.DATABASE_URL is deprecated"
        ):
            config.DATABASE_URL = "bolt://test:test@localhost:7687"

        with pytest.warns(
            DeprecationWarning, match="Setting config.FORCE_TIMEZONE is deprecated"
        ):
            config.FORCE_TIMEZONE = True

        with pytest.warns(
            DeprecationWarning, match="Setting config.SLOW_QUERIES is deprecated"
        ):
            config.SLOW_QUERIES = 1.0

    def test_deprecation_warning_only_once_per_attribute(self):
        """Test that deprecation warnings are only shown once per attribute."""
        # First access should show warning
        with pytest.warns(DeprecationWarning):
            _ = config.DATABASE_URL

        # Second access should not show warning
        with warnings.catch_warnings():
            warnings.simplefilter("error")  # Turn warnings into errors
            _ = config.DATABASE_URL  # Should not raise

    def test_deprecation_warning_message_content(self):
        """Test that deprecation warning messages contain helpful migration information."""
        with pytest.warns(DeprecationWarning) as warning_info:
            _ = config.DATABASE_URL

        warning = warning_info[0]
        assert "Accessing config.DATABASE_URL is deprecated" in str(warning.message)
        assert "from neomodel import get_config" in str(warning.message)
        assert "config.database_url" in str(warning.message)

    def test_deprecation_warning_message_for_setting(self):
        """Test that deprecation warning messages for setting contain helpful migration information."""
        with pytest.warns(DeprecationWarning) as warning_info:
            config.FORCE_TIMEZONE = True

        warning = warning_info[0]
        assert "Setting config.FORCE_TIMEZONE is deprecated" in str(warning.message)
        assert "from neomodel import get_config" in str(warning.message)
        assert "config.force_timezone = value" in str(warning.message)

    def test_clear_deprecation_warnings_resets_state(self):
        """Test that clear_deprecation_warnings resets the warning state."""
        # First access should show warning
        with pytest.warns(DeprecationWarning):
            _ = config.DATABASE_URL

        # Clear warnings
        clear_deprecation_warnings()

        # Next access should show warning again
        with pytest.warns(DeprecationWarning):
            _ = config.DATABASE_URL

    def test_modern_api_no_deprecation_warnings(self):
        """Test that the modern API does not trigger deprecation warnings."""
        with warnings.catch_warnings():
            warnings.simplefilter("error")  # Turn warnings into errors

            # Modern API should not trigger warnings
            config_obj = get_config()
            _ = config_obj.database_url
            _ = config_obj.force_timezone
            _ = config_obj.cypher_debug

            config_obj.database_url = "bolt://test:test@localhost:7687"
            config_obj.force_timezone = True
            config_obj.slow_queries = 1.0

    # Pytest fixture to run after the last test in this file and reset config to default
    # This prevents interference for subsequent tests in other files.
    @pytest.fixture(autouse=True)
    def teardown(self):
        yield
        reset_config()
