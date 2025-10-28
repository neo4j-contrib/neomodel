"""
Neomodel configuration module.

This module provides a modern dataclass-based configuration system with validation
and environment variable support, while maintaining backward compatibility.
"""

import os
import sys
import warnings
from dataclasses import dataclass, field, fields
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import neo4j
from neo4j import Driver

from neomodel._version import __version__


@dataclass
class NeomodelConfig:
    """
    Neomodel configuration using dataclasses with validation and environment variable support.

    This class provides a modern, type-safe configuration system that can be loaded
    from environment variables and validated at startup.
    """

    # Connection settings
    database_url: str = field(
        default="bolt://neo4j:foobarbaz@localhost:7687",
        metadata={
            "env_var": "NEOMODEL_DATABASE_URL",
            "description": "Graph database connection URL",
        },
    )
    driver: Driver | None = field(
        default=None,
        metadata={"env_var": None, "description": "Custom database driver instance"},
    )
    database_name: str | None = field(
        default=None,
        metadata={
            "env_var": "NEOMODEL_DATABASE_NAME",
            "description": "Database name for neomodel-managed driver instance",
        },
    )

    # Driver configuration (for neomodel-managed connections)
    connection_acquisition_timeout: float = field(
        default=60.0,
        metadata={
            "env_var": "NEOMODEL_CONNECTION_ACQUISITION_TIMEOUT",
            "description": "Connection acquisition timeout in seconds",
        },
    )
    connection_timeout: float = field(
        default=30.0,
        metadata={
            "env_var": "NEOMODEL_CONNECTION_TIMEOUT",
            "description": "Connection timeout in seconds",
        },
    )
    encrypted: bool = field(
        default=False,
        metadata={
            "env_var": "NEOMODEL_ENCRYPTED",
            "description": "Enable encrypted connections",
        },
    )
    keep_alive: bool = field(
        default=True,
        metadata={
            "env_var": "NEOMODEL_KEEP_ALIVE",
            "description": "Enable keep-alive connections",
        },
    )
    max_connection_lifetime: int = field(
        default=3600,
        metadata={
            "env_var": "NEOMODEL_MAX_CONNECTION_LIFETIME",
            "description": "Maximum connection lifetime in seconds",
        },
    )
    max_connection_pool_size: int = field(
        default=100,
        metadata={
            "env_var": "NEOMODEL_MAX_CONNECTION_POOL_SIZE",
            "description": "Maximum connection pool size",
        },
    )
    max_transaction_retry_time: float = field(
        default=30.0,
        metadata={
            "env_var": "NEOMODEL_MAX_TRANSACTION_RETRY_TIME",
            "description": "Maximum transaction retry time in seconds",
        },
    )
    resolver: Any | None = field(
        default=None,
        metadata={
            "env_var": None,
            "description": "Custom resolver for connection routing",
        },
    )
    trusted_certificates: Any = field(
        default_factory=neo4j.TrustSystemCAs,
        metadata={
            "env_var": None,
            "description": "Trusted certificates for encrypted connections",
        },
    )
    user_agent: str = field(
        default=f"neomodel/v{__version__}",
        metadata={
            "env_var": "NEOMODEL_USER_AGENT",
            "description": "User agent string for connections",
        },
    )

    # Neomodel-specific settings
    force_timezone: bool = field(
        default=False,
        metadata={
            "env_var": "NEOMODEL_FORCE_TIMEZONE",
            "description": "Force timezone-aware datetime objects",
        },
    )
    soft_cardinality_check: bool = field(
        default=False,
        metadata={
            "env_var": "NEOMODEL_SOFT_CARDINALITY_CHECK",
            "description": "Enable soft cardinality checking (warnings only)",
        },
    )
    cypher_debug: bool = field(
        default=False,
        metadata={
            "env_var": "NEOMODEL_CYPHER_DEBUG",
            "description": "Enable Cypher debug logging",
        },
    )
    slow_queries: float = field(
        default=0.0,
        metadata={
            "env_var": "NEOMODEL_SLOW_QUERIES",
            "description": "Threshold in seconds for slow query logging (0 = disabled)",
        },
    )

    def __post_init__(self):
        """Validate configuration after initialization."""
        self._validate_config()

    def __setattr__(self, name: str, value: Any) -> None:
        """Set attribute and validate configuration."""
        super().__setattr__(name, value)
        # Only validate if we're not in __init__ or __post_init__
        if hasattr(self, "_initialized"):
            # Don't validate here - let the calling code handle validation
            pass
        else:
            # Mark as initialized after first attribute set
            if name != "_initialized":
                self._initialized = True

    def _validate_config(self) -> None:
        """Validate configuration values."""
        # Validate database URL format
        if self.database_url:
            try:
                parsed = urlparse(self.database_url)
                if not parsed.scheme or not parsed.netloc:
                    raise ValueError(
                        f"Invalid database URL format: {self.database_url}"
                    )
            except Exception as e:
                raise ValueError(f"Invalid database URL: {e}") from e

        # Validate numeric values
        if self.connection_acquisition_timeout <= 0:
            raise ValueError("connection_acquisition_timeout must be positive")

        if self.connection_timeout <= 0:
            raise ValueError("connection_timeout must be positive")

        if self.max_connection_lifetime <= 0:
            raise ValueError("max_connection_lifetime must be positive")

        if self.max_connection_pool_size <= 0:
            raise ValueError("max_connection_pool_size must be positive")

        if self.max_transaction_retry_time <= 0:
            raise ValueError("max_transaction_retry_time must be positive")

        # Validate slow_queries threshold
        if self.slow_queries < 0:
            raise ValueError("slow_queries must be non-negative")

    @classmethod
    def from_env(cls) -> "NeomodelConfig":
        """Create configuration from environment variables."""
        config_data: dict[str, Any] = {}

        # Get all fields with their metadata
        for field_info in fields(cls):
            env_var = field_info.metadata.get("env_var")
            if env_var and env_var in os.environ:
                value = os.environ[env_var]
                field_type = field_info.type

                # Convert string values to appropriate types
                if field_type == bool:
                    config_data[field_info.name] = value.lower() in (
                        "true",
                        "1",
                        "yes",
                        "on",
                    )
                elif field_type == int:
                    config_data[field_info.name] = int(value)
                elif field_type == float:
                    config_data[field_info.name] = float(value)
                else:
                    config_data[field_info.name] = value

        return cls(**config_data)

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        result: dict[str, Any] = {}
        for field_info in fields(self):
            value = getattr(self, field_info.name)
            # Skip non-serializable values
            if field_info.name not in ("driver", "resolver", "trusted_certificates"):
                result[field_info.name] = value
        return result

    def update(self, **kwargs) -> None:
        """Update configuration values."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                warnings.warn(f"Unknown configuration option: {key}")

        # Re-validate after update
        self._validate_config()  # pylint: disable=protected-access


# Global configuration instance
_config: Optional[NeomodelConfig] = None


def get_config() -> NeomodelConfig:
    """Get the global configuration instance."""
    global _config  # noqa: PLW0603 - usage of 'global' is required here for module-level singleton pattern
    if _config is None:
        _config = NeomodelConfig.from_env()
    return _config


def set_config(config: NeomodelConfig) -> None:
    """Set the global configuration instance."""
    global _config  # noqa: PLW0603 - usage of 'global' is required here for module-level singleton pattern
    _config = config


def reset_config() -> None:
    """Reset the global configuration to default values."""
    global _config  # noqa: PLW0603 - usage of 'global' is required here for module-level singleton pattern
    _config = None


def clear_deprecation_warnings() -> None:
    """Clear the set of deprecation warnings that have been shown.

    This is primarily useful for testing purposes to reset the warning state.
    """
    global _legacy_attr_warnings
    _legacy_attr_warnings.clear()


# Backward compatibility: Create module-level attributes that delegate to the config instance
_legacy_attr_warnings: set[str] = set()


def _get_attr(name: str) -> Any:
    """Get attribute from the global config instance."""
    # Issue deprecation warning for legacy attribute access
    if name not in _legacy_attr_warnings:
        _legacy_attr_warnings.add(name)
        warnings.warn(
            f"Accessing config.{name.upper()} is deprecated and will be removed in a future version. Use the modern configuration API instead: "
            f"from neomodel import get_config; config = get_config(); config.{name}",
            DeprecationWarning,
            stacklevel=3,
        )

    config = get_config()
    return getattr(config, name)


def _set_attr(name: str, value: Any) -> None:
    """Set attribute on the global config instance."""
    # Issue deprecation warning for legacy attribute setting
    if name not in _legacy_attr_warnings:
        _legacy_attr_warnings.add(name)
        warnings.warn(
            f"Setting config.{name.upper()} is deprecated and will be removed in a future version. Use the modern configuration API instead: "
            f"from neomodel import get_config; config = get_config(); config.{name} = value",
            DeprecationWarning,
            stacklevel=3,
        )

    config = get_config()
    original_value = getattr(config, name)
    setattr(config, name, value)
    try:
        config._validate_config()  # pylint: disable=protected-access
    except ValueError:
        # If validation fails, revert the change
        setattr(config, name, original_value)
        raise


# Create module-level properties for backward compatibility
class _ConfigModule:
    """Module-level configuration access for backward compatibility."""

    @property
    def DATABASE_URL(
        self,
    ) -> str:
        return _get_attr("database_url")

    @DATABASE_URL.setter
    def DATABASE_URL(self, value: str) -> None:
        _set_attr("database_url", value)

    @property
    def DRIVER(
        self,
    ) -> Driver | None:
        return _get_attr("driver")

    @DRIVER.setter
    def DRIVER(self, value: Driver | None) -> None:
        _set_attr("driver", value)

    @property
    def DATABASE_NAME(
        self,
    ) -> str | None:
        return _get_attr("database_name")

    @DATABASE_NAME.setter
    def DATABASE_NAME(self, value: str | None) -> None:
        _set_attr("database_name", value)

    @property
    def CONNECTION_ACQUISITION_TIMEOUT(
        self,
    ) -> float:
        return _get_attr("connection_acquisition_timeout")

    @CONNECTION_ACQUISITION_TIMEOUT.setter
    def CONNECTION_ACQUISITION_TIMEOUT(self, value: float) -> None:
        _set_attr("connection_acquisition_timeout", value)

    @property
    def CONNECTION_TIMEOUT(
        self,
    ) -> float:
        return _get_attr("connection_timeout")

    @CONNECTION_TIMEOUT.setter
    def CONNECTION_TIMEOUT(self, value: float) -> None:
        _set_attr("connection_timeout", value)

    @property
    def ENCRYPTED(
        self,
    ) -> bool:
        return _get_attr("encrypted")

    @ENCRYPTED.setter
    def ENCRYPTED(self, value: bool) -> None:
        _set_attr("encrypted", value)

    @property
    def KEEP_ALIVE(
        self,
    ) -> bool:
        return _get_attr("keep_alive")

    @KEEP_ALIVE.setter
    def KEEP_ALIVE(self, value: bool) -> None:
        _set_attr("keep_alive", value)

    @property
    def MAX_CONNECTION_LIFETIME(
        self,
    ) -> int:
        return _get_attr("max_connection_lifetime")

    @MAX_CONNECTION_LIFETIME.setter
    def MAX_CONNECTION_LIFETIME(self, value: int) -> None:
        _set_attr("max_connection_lifetime", value)

    @property
    def MAX_CONNECTION_POOL_SIZE(
        self,
    ) -> int:
        return _get_attr("max_connection_pool_size")

    @MAX_CONNECTION_POOL_SIZE.setter
    def MAX_CONNECTION_POOL_SIZE(self, value: int) -> None:
        _set_attr("max_connection_pool_size", value)

    @property
    def MAX_TRANSACTION_RETRY_TIME(
        self,
    ) -> float:
        return _get_attr("max_transaction_retry_time")

    @MAX_TRANSACTION_RETRY_TIME.setter
    def MAX_TRANSACTION_RETRY_TIME(self, value: float) -> None:
        _set_attr("max_transaction_retry_time", value)

    @property
    def RESOLVER(
        self,
    ) -> Any | None:
        return _get_attr("resolver")

    @RESOLVER.setter
    def RESOLVER(self, value: Any | None) -> None:
        _set_attr("resolver", value)

    @property
    def TRUSTED_CERTIFICATES(
        self,
    ) -> Any:
        return _get_attr("trusted_certificates")

    @TRUSTED_CERTIFICATES.setter
    def TRUSTED_CERTIFICATES(self, value: Any) -> None:
        _set_attr("trusted_certificates", value)

    @property
    def USER_AGENT(
        self,
    ) -> str:
        return _get_attr("user_agent")

    @USER_AGENT.setter
    def USER_AGENT(self, value: str) -> None:
        _set_attr("user_agent", value)

    @property
    def FORCE_TIMEZONE(
        self,
    ) -> bool:
        return _get_attr("force_timezone")

    @FORCE_TIMEZONE.setter
    def FORCE_TIMEZONE(self, value: bool) -> None:
        _set_attr("force_timezone", value)

    @property
    def SOFT_CARDINALITY_CHECK(
        self,
    ) -> bool:
        return _get_attr("soft_cardinality_check")

    @SOFT_CARDINALITY_CHECK.setter
    def SOFT_CARDINALITY_CHECK(self, value: bool) -> None:
        _set_attr("soft_cardinality_check", value)

    @property
    def CYPHER_DEBUG(
        self,
    ) -> bool:
        return _get_attr("cypher_debug")

    @CYPHER_DEBUG.setter
    def CYPHER_DEBUG(self, value: bool) -> None:
        _set_attr("cypher_debug", value)

    @property
    def SLOW_QUERIES(
        self,
    ) -> float:
        return _get_attr("slow_queries")

    @SLOW_QUERIES.setter
    def SLOW_QUERIES(self, value: float) -> None:
        _set_attr("slow_queries", value)


# Create the module instance for backward compatibility
_current_module = sys.modules[__name__]
_config_module = _ConfigModule()

# Replace the module with the config module instance
sys.modules[__name__] = _config_module  # type: ignore[assignment]

# Copy all attributes from the original module to maintain backward compatibility
for attr_name in dir(_current_module):
    if not attr_name.startswith("_") and not hasattr(_config_module, attr_name):
        setattr(_config_module, attr_name, getattr(_current_module, attr_name))
