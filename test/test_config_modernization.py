"""
Tests for the modernized configuration system.

This module tests the new dataclass-based configuration system with validation
and environment variable support.
"""

import os
from unittest.mock import patch

import pytest

from neomodel import NeomodelConfig, config, get_config, reset_config, set_config


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


class TestBackwardCompatibility:
    """Test backward compatibility with existing config usage."""

    def test_module_level_access(self):
        """Test that module-level attributes work as before."""
        # Test reading values
        assert isinstance(config.DATABASE_URL, str)
        assert isinstance(config.FORCE_TIMEZONE, bool)
        assert isinstance(config.SOFT_CARDINALITY_CHECK, bool)
        assert isinstance(config.CYPHER_DEBUG, bool)
        assert isinstance(config.SLOW_QUERIES, float)

        # Test setting values
        original_url = config.DATABASE_URL
        config.DATABASE_URL = "bolt://test:test@localhost:7687"
        assert config.DATABASE_URL == "bolt://test:test@localhost:7687"

        # Restore original value
        config.DATABASE_URL = original_url

    def test_validation_on_set(self):
        """Test that validation occurs when setting module-level attributes."""
        with pytest.raises(ValueError, match="connection_timeout must be positive"):
            config.CONNECTION_TIMEOUT = -1

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
            assert config.ENCRYPTED is True
            assert config.KEEP_ALIVE is False
            assert config.CYPHER_DEBUG is False
            assert config.SLOW_QUERIES == 0.5


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
