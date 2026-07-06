"""
Database facade for the async neomodel module.

``AsyncDatabase`` is the singleton ``adb`` that user code and the rest of
neomodel talk to. It is a thin facade that composes three collaborators and
delegates to them:

* :class:`~neomodel.async_.connection.AsyncConnectionManager` - driver, URL,
  server version/edition, sessions and transactions (the shared state).
* :class:`~neomodel.async_.query.AsyncQueryRunner` - Cypher execution, streaming
  and object resolution.
* :class:`~neomodel.async_.schema.AsyncSchemaManager` - index/constraint
  installation and schema admin.

The node-class registry lives in :mod:`neomodel.async_._registry`.

``ensure_connection`` and ``_redact_params`` are re-exported here for backward
compatibility with code that imports them from this module.
"""

from typing import TYPE_CHECKING, Any, AsyncIterator, TextIO

from neo4j import AsyncDriver, AsyncSession, AsyncTransaction
from neo4j.api import Bookmarks

from neomodel.async_._registry import registry
from neomodel.async_.connection import AsyncConnectionManager, ensure_connection
from neomodel.async_.query import AsyncQueryRunner, _redact_params
from neomodel.async_.schema import AsyncSchemaManager
from neomodel.constants import (
    ACCESS_MODE_READ,
    ACCESS_MODE_WRITE,
    ENTERPRISE_EDITION_TAG,
)
from neomodel.exceptions import FeatureNotSupported

# Re-exported for backward compatibility (imported from this module elsewhere).
__all__ = ["AsyncDatabase", "adb", "ensure_connection", "_redact_params"]

if TYPE_CHECKING:
    from neomodel.async_.transaction import AsyncTransactionProxy, ImpersonationHandler


class AsyncDatabase:
    """
    A singleton object via which all operations from neomodel to the Neo4j backend are handled with.

    This class enforces singleton behavior - only one instance can exist at a time.
    The singleton instance is accessible via the module-level 'adb' variable.

    It is a facade over an ``AsyncConnectionManager`` (connection/transaction
    state), an ``AsyncQueryRunner`` (query execution) and an
    ``AsyncSchemaManager`` (index/constraint management).
    """

    # Singleton instance tracking
    _instance: "AsyncDatabase | None" = None
    _initialized: bool = False

    def __new__(cls) -> "AsyncDatabase":
        """
        Enforce singleton pattern - only one instance can exist.

        Returns:
            AsyncDatabase: The singleton instance
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        # Prevent re-initialization of the singleton instance
        if AsyncDatabase._initialized:
            return

        # Compose the collaborators. The connection manager holds the shared
        # state; the query runner and schema manager operate against it. The
        # connection manager needs the query runner to detect the server
        # version, so wire it in after construction.
        self._connection = AsyncConnectionManager()
        self._query = AsyncQueryRunner(self._connection)
        self._connection._query = self._query
        self._schema = AsyncSchemaManager(self._connection, self._query)

        AsyncDatabase._initialized = True

    @classmethod
    def get_instance(cls) -> "AsyncDatabase":
        """
        Get the singleton instance of AsyncDatabase.

        Returns:
            AsyncDatabase: The singleton instance
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    async def reset_instance(cls) -> None:
        """
        Reset the singleton instance. This should only be used for testing purposes.

        Warning: This will close any existing connections and reset all state.
        """
        if cls._instance is not None:
            # Close any existing connections
            await cls._instance.close_connection()

        cls._instance = None
        cls._initialized = False

    # ------------------------------------------------------------------ #
    # Class registry (standalone object, exposed for backward compat)
    # ------------------------------------------------------------------ #
    @property
    def _NODE_CLASS_REGISTRY(self) -> dict[frozenset, Any]:
        return registry._node_class_registry

    @property
    def _DB_SPECIFIC_CLASS_REGISTRY(self) -> dict[str, dict[frozenset, Any]]:
        return registry._db_specific_class_registry

    # ------------------------------------------------------------------ #
    # Shared connection state (delegated to the connection manager)
    # ------------------------------------------------------------------ #
    @property
    def driver(self) -> AsyncDriver | None:
        return self._connection.driver

    @driver.setter
    def driver(self, value: AsyncDriver | None) -> None:
        self._connection.driver = value

    @property
    def _owns_driver(self) -> bool:
        return self._connection._owns_driver

    @_owns_driver.setter
    def _owns_driver(self, value: bool) -> None:
        self._connection._owns_driver = value

    @property
    def _connection_lock(self) -> Any:
        return self._connection._connection_lock

    @property
    def url(self) -> str | None:
        return self._connection.url

    @url.setter
    def url(self, value: str | None) -> None:
        self._connection.url = value

    @property
    def _connection_url(self) -> str | None:
        return self._connection._connection_url

    @_connection_url.setter
    def _connection_url(self, value: str | None) -> None:
        self._connection._connection_url = value

    @property
    def _database_version(self) -> str | None:
        return self._connection._database_version

    @_database_version.setter
    def _database_version(self, value: str | None) -> None:
        self._connection._database_version = value

    @property
    def _database_edition(self) -> str | None:
        return self._connection._database_edition

    @_database_edition.setter
    def _database_edition(self, value: str | None) -> None:
        self._connection._database_edition = value

    @property
    def _active_transaction(self) -> AsyncTransaction | None:
        return self._connection._active_transaction

    @_active_transaction.setter
    def _active_transaction(self, value: AsyncTransaction | None) -> None:
        self._connection._active_transaction = value

    @property
    def _session(self) -> AsyncSession | None:
        return self._connection._session

    @_session.setter
    def _session(self, value: AsyncSession | None) -> None:
        self._connection._session = value

    @property
    def _database_name(self) -> str | None:
        return self._connection._database_name

    @_database_name.setter
    def _database_name(self, value: str | None) -> None:
        self._connection._database_name = value

    @property
    def impersonated_user(self) -> str | None:
        return self._connection.impersonated_user

    @impersonated_user.setter
    def impersonated_user(self, value: str | None) -> None:
        self._connection.impersonated_user = value

    @property
    def _parallel_runtime(self) -> bool | None:
        return self._connection._parallel_runtime

    @_parallel_runtime.setter
    def _parallel_runtime(self, value: bool | None) -> None:
        self._connection._parallel_runtime = value

    # ------------------------------------------------------------------ #
    # Connection lifecycle and server facts (delegated to connection)
    # ------------------------------------------------------------------ #
    async def set_connection(
        self, url: str | None = None, driver: AsyncDriver | None = None
    ) -> None:
        await self._connection.set_connection(url=url, driver=driver)

    def _parse_driver_from_url(self, url: str) -> None:
        self._connection._parse_driver_from_url(url=url)

    async def close_connection(self) -> None:
        await self._connection.close_connection()

    @property
    async def database_version(self) -> str | None:
        return await self._connection.database_version

    @property
    async def database_edition(self) -> str | None:
        return await self._connection.database_edition

    async def begin(
        self,
        access_mode: str | None = ACCESS_MODE_WRITE,
        timeout: float | None = None,
        **parameters: Any,
    ) -> None:
        await self._connection.begin(
            access_mode=access_mode, timeout=timeout, **parameters
        )

    async def commit(self) -> Bookmarks:
        return await self._connection.commit()

    async def rollback(self) -> None:
        await self._connection.rollback()

    async def get_id_method(self) -> str:
        return await self._connection.get_id_method()

    async def parse_element_id(self, element_id: str | None) -> str | int:
        return await self._connection.parse_element_id(element_id)

    async def version_is_higher_than(self, version_tag: str) -> bool:
        return await self._connection.version_is_higher_than(version_tag)

    async def edition_is_enterprise(self) -> bool:
        return await self._connection.edition_is_enterprise()

    async def parallel_runtime_available(self) -> bool:
        return await self._connection.parallel_runtime_available()

    # ------------------------------------------------------------------ #
    # Transaction context managers and impersonation
    # ------------------------------------------------------------------ #
    @property
    def transaction(self) -> "AsyncTransactionProxy":
        """
        Returns the current transaction object
        """
        from neomodel.async_.transaction import AsyncTransactionProxy

        return AsyncTransactionProxy(self)

    @property
    def write_transaction(self) -> "AsyncTransactionProxy":
        from neomodel.async_.transaction import AsyncTransactionProxy

        return AsyncTransactionProxy(self, access_mode=ACCESS_MODE_WRITE)

    @property
    def read_transaction(self) -> "AsyncTransactionProxy":
        from neomodel.async_.transaction import AsyncTransactionProxy

        return AsyncTransactionProxy(self, access_mode=ACCESS_MODE_READ)

    @property
    def parallel_read_transaction(self) -> "AsyncTransactionProxy":
        from neomodel.async_.transaction import AsyncTransactionProxy

        return AsyncTransactionProxy(
            self, access_mode=ACCESS_MODE_READ, parallel_runtime=True
        )

    async def impersonate(self, user: str) -> "ImpersonationHandler":
        """All queries executed within this context manager will be executed as impersonated user

        Args:
            user (str): User to impersonate

        Returns:
            ImpersonationHandler: Context manager to set/unset the user to impersonate
        """
        from neomodel.async_.transaction import ImpersonationHandler

        db_edition = await self.database_edition
        if db_edition != ENTERPRISE_EDITION_TAG:
            raise FeatureNotSupported(
                "Impersonation is only available in Neo4j Enterprise edition"
            )
        return ImpersonationHandler(self, impersonated_user=user)

    # ------------------------------------------------------------------ #
    # Query execution (delegated to the query runner)
    # ------------------------------------------------------------------ #
    async def cypher_query(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        handle_unique: bool = True,
        retry_on_session_expire: bool = False,
        resolve_objects: bool = False,
    ) -> tuple[list, tuple[str, ...]]:
        return await self._query.cypher_query(
            query,
            params,
            handle_unique,
            retry_on_session_expire,
            resolve_objects,
        )

    def _stream_cypher_query(
        self,
        session: AsyncSession | AsyncTransaction,
        query: str,
        params: dict[str, Any],
        handle_unique: bool,
        resolve_objects: bool,
    ) -> AsyncIterator[tuple[list, tuple[str, ...]]]:
        return self._query._stream_cypher_query(
            session, query, params, handle_unique, resolve_objects
        )

    def _object_resolution(self, object_to_resolve: Any) -> Any:
        return self._query._object_resolution(object_to_resolve)

    # ------------------------------------------------------------------ #
    # Schema management (delegated to the schema manager)
    # ------------------------------------------------------------------ #
    async def list_indexes(self, exclude_token_lookup: bool = False) -> list[dict]:
        return await self._schema.list_indexes(
            exclude_token_lookup=exclude_token_lookup
        )

    async def list_constraints(self) -> list[dict]:
        return await self._schema.list_constraints()

    async def change_neo4j_password(self, user: str, new_password: str) -> None:
        await self._schema.change_neo4j_password(user, new_password)

    async def clear_neo4j_database(
        self, clear_constraints: bool = False, clear_indexes: bool = False
    ) -> None:
        await self._schema.clear_neo4j_database(
            clear_constraints=clear_constraints, clear_indexes=clear_indexes
        )

    async def drop_constraints(
        self, quiet: bool = True, stdout: TextIO | None = None
    ) -> None:
        await self._schema.drop_constraints(quiet=quiet, stdout=stdout)

    async def drop_indexes(
        self, quiet: bool = True, stdout: TextIO | None = None
    ) -> None:
        await self._schema.drop_indexes(quiet=quiet, stdout=stdout)

    async def remove_all_labels(self, stdout: TextIO | None = None) -> None:
        await self._schema.remove_all_labels(stdout=stdout)

    async def install_all_labels(self, stdout: TextIO | None = None) -> None:
        await self._schema.install_all_labels(stdout=stdout)

    async def install_labels(
        self, cls: Any, quiet: bool = True, stdout: TextIO | None = None
    ) -> None:
        await self._schema.install_labels(cls, quiet=quiet, stdout=stdout)


# Create a singleton instance of the database object
adb = AsyncDatabase.get_instance()
