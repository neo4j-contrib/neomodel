"""
Connection management for the neomodel module.

``ConnectionManager`` owns all of the connection state (the driver and the
facts derived from it, plus the per-context session/transaction/database/
impersonation settings) and the connection, transaction and server-version
lifecycle. ``QueryRunner`` and ``SchemaManager`` operate against it,
and ``Database`` exposes it as a facade.
"""

from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, Callable
from urllib.parse import urlsplit

from neo4j import (
    DEFAULT_DATABASE,
    Driver,
    GraphDatabase,
    Session,
    Transaction,
    basic_auth,
)
from neo4j.api import Bookmarks
from neo4j.exceptions import ServiceUnavailable

from neomodel._async_compat.util import Lock
from neomodel.config import get_config
from neomodel.constants import (
    ACCESS_MODE_WRITE,
    ELEMENT_ID_METHOD,
    ENTERPRISE_EDITION_TAG,
    LEGACY_ID_METHOD,
    NO_SESSION_OPEN,
    NO_TRANSACTION_IN_PROGRESS,
    UNKNOWN_SERVER_VERSION,
    VERSION_LEGACY_ID,
    VERSION_PARALLEL_RUNTIME_SUPPORT,
)
from neomodel.util import version_tag_to_integer

if TYPE_CHECKING:
    from neomodel.sync_.query import QueryRunner


def ensure_connection(func: Callable) -> Callable:
    """Decorator that ensures a connection is established before executing the decorated function.

    Works both on the connection manager itself and on objects that hold a
    reference to it under ``self.db`` (e.g. the query runner).

    Args:
        func (callable): The function to be decorated.

    Returns:
        callable: The decorated function.
    """

    def wrapper(self: Any, *args: Any, **kwargs: Any) -> Callable:
        # Sort out where to find url
        if hasattr(self, "db"):
            _db = self.db
        else:
            _db = self

        if not _db.driver:
            # The driver is process-wide (shared across threads and async
            # contexts). Guard the lazy build with a lock and re-check inside it
            # so concurrent first callers establish a single driver/pool instead
            # of each racing to create their own.
            with _db._connection_lock:
                if not _db.driver:
                    config = get_config()
                    if hasattr(config, "database_url") and config.database_url:
                        _db.set_connection(url=config.database_url)
                    elif hasattr(config, "driver") and config.driver:
                        _db.set_connection(driver=config.driver)
                    else:
                        raise ValueError(
                            "No Neo4j connection has been configured. Set "
                            "`neomodel.config.DATABASE_URL` (or the NEOMODEL_DATABASE_URL "
                            "environment variable), provide a driver via "
                            "`neomodel.config.DRIVER`, or call `db.set_connection(...)` "
                            "before running queries."
                        )

        return func(self, *args, **kwargs)

    return wrapper


class ConnectionManager:
    """Owns the driver, connection state and transaction/version lifecycle."""

    def __init__(self) -> None:
        # Set by the owning AsyncDatabase so version detection can run a query.
        self._query: "QueryRunner | None" = None

        # Process-wide state. A neo4j driver is thread-safe and holds a single
        # connection pool that is meant to be shared across the whole process,
        # so the driver and the connection facts derived from it live on the
        # singleton rather than per-context. ``_connection_lock`` guards the
        # lazy creation of the driver against concurrent first callers.
        self._connection_lock = Lock()
        self.driver: Driver | None = None
        # Whether neomodel created the current driver (via a URL) and is
        # therefore responsible for closing it. A user-supplied driver is owned
        # by the caller and is never closed implicitly when the connection is
        # replaced.
        self._owns_driver: bool = False
        # ``url`` is the public, password-redacted connection URL (safe to log
        # or inspect). ``_connection_url`` keeps the credential-bearing URL
        # privately, only used internally to re-establish the connection
        # (e.g. on session expiry).
        self.url: str | None = None
        self._connection_url: str | None = None
        # Server-level facts: the same for every context talking to this driver.
        self._database_version: str | None = None
        self._database_edition: str | None = None

        # Context-local state. These must not leak across threads or async
        # tasks: each logical unit of work gets its own session/transaction,
        # its own impersonation and runtime settings, and may target a
        # different database (used for per-database class resolution).
        self.__active_transaction: ContextVar[Transaction | None] = ContextVar(
            "_active_transaction", default=None
        )
        self.__session: ContextVar[Session | None] = ContextVar(
            "_session", default=None
        )
        self.__database_name: ContextVar[str | None] = ContextVar(
            "_database_name", default=DEFAULT_DATABASE
        )
        self.__impersonated_user: ContextVar[str | None] = ContextVar(
            "impersonated_user", default=None
        )
        self.__parallel_runtime: ContextVar[bool | None] = ContextVar(
            "_parallel_runtime", default=False
        )

    @property
    def _active_transaction(self) -> Transaction | None:
        return self.__active_transaction.get()

    @_active_transaction.setter
    def _active_transaction(self, value: Transaction | None) -> None:
        self.__active_transaction.set(value)

    @property
    def _session(self) -> Session | None:
        return self.__session.get()

    @_session.setter
    def _session(self, value: Session | None) -> None:
        self.__session.set(value)

    @property
    def _database_name(self) -> str | None:
        return self.__database_name.get()

    @_database_name.setter
    def _database_name(self, value: str | None) -> None:
        self.__database_name.set(value)

    @property
    def impersonated_user(self) -> str | None:
        return self.__impersonated_user.get()

    @impersonated_user.setter
    def impersonated_user(self, value: str | None) -> None:
        self.__impersonated_user.set(value)

    @property
    def _parallel_runtime(self) -> bool | None:
        return self.__parallel_runtime.get()

    @_parallel_runtime.setter
    def _parallel_runtime(self, value: bool | None) -> None:
        self.__parallel_runtime.set(value)

    @staticmethod
    def _redact_url_password(url: str) -> str:
        """
        Return a copy of a Neo4j connection URL with the password component
        replaced by ``***`` so the URL can be stored or surfaced in error
        messages without leaking credentials.
        """
        scheme_index = url.find("://")
        at_index = url.rfind("@")
        if scheme_index == -1 or at_index == -1:
            # No userinfo section, so there is no password to redact.
            return url
        credentials_start = scheme_index + len("://")
        credentials = url[credentials_start:at_index]
        if ":" not in credentials:
            return url
        username = credentials.split(":", 1)[0]
        return f"{url[:credentials_start]}{username}:***{url[at_index:]}"

    def set_connection(
        self, url: str | None = None, driver: Driver | None = None
    ) -> None:
        """
        Sets the connection up and relevant internal. This can be done using a Neo4j URL or a driver instance.

        The driver (and the server facts derived from it) is shared across the
        whole process, so calling this replaces the connection for every thread
        and context, not just the calling one. The target database name is
        context-local: it is set for the current context here and inherited by
        any child contexts spawned afterwards.

        Args:
            url (str): Optionally, Neo4j URL in the form protocol://username:password@hostname:port/dbname.
            When provided, a Neo4j driver instance will be created by neomodel.

            driver (neo4j.Driver): Optionally, a pre-created driver instance.
            When provided, neomodel will not create a driver instance but use this one instead.
        """
        # Replacing the process-wide driver: close the previous one if neomodel
        # created it, so its connection pool is not leaked. A user-supplied
        # driver is left untouched - its lifecycle belongs to the caller.
        if self.driver is not None and self._owns_driver:
            self.driver.close()
            self.driver = None
            self._owns_driver = False

        if driver:
            self.driver = driver
            self._owns_driver = False
            config = get_config()
            if hasattr(config, "database_name") and config.database_name:
                self._database_name = config.database_name
        elif url:
            self._parse_driver_from_url(url=url)

        self._active_transaction = None
        # Set to default database if it hasn't been set before
        if self._database_name is None:
            self._database_name = DEFAULT_DATABASE

        # Getting the information about the database version requires a connection to the database
        self._database_version = None
        self._database_edition = None
        self._update_database_version()

    def _parse_driver_from_url(self, url: str) -> None:
        """Parse the driver information from the given URL and initialize the driver.

        Args:
            url (str): The URL to parse.

        Raises:
            ValueError: If the URL format is not as expected.

        Returns:
            None - Sets the driver and database_name as class properties
        """
        valid_schemas = [
            "bolt",
            "bolt+s",
            "bolt+ssc",
            "bolt+routing",
            "neo4j",
            "neo4j+s",
            "neo4j+ssc",
        ]

        # Split the URL by its delimiters rather than substituting the password
        # substring: this keeps passwords containing characters like "@" or ":"
        # intact and avoids corrupting the URL when the password happens to match
        # another part of it. Credentials are split off the last "@" and the
        # username from the first ":", so only the very first ":" is treated as
        # the user/password separator.
        split_url = urlsplit(url)
        scheme = split_url.scheme
        if "@" not in split_url.netloc or scheme not in valid_schemas:
            raise ValueError(
                "Expecting url format: bolt://user:password@localhost:7687 got "
                f"{self._redact_url_password(url)}"
            )

        credentials, hostname = split_url.netloc.rsplit("@", 1)
        username, separator, password = credentials.partition(":")
        if not separator:
            raise ValueError(
                "Expecting url format: bolt://user:password@localhost:7687 got "
                f"{self._redact_url_password(url)}"
            )
        database_name = split_url.path.strip("/")

        config = get_config()
        options = {
            "auth": basic_auth(username, password),
            "connection_acquisition_timeout": config.connection_acquisition_timeout,
            "connection_timeout": config.connection_timeout,
            "keep_alive": config.keep_alive,
            "max_connection_lifetime": config.max_connection_lifetime,
            "max_connection_pool_size": config.max_connection_pool_size,
            "max_transaction_retry_time": config.max_transaction_retry_time,
            "resolver": config.resolver,
            "user_agent": config.user_agent,
        }

        if "+s" not in scheme:
            options["encrypted"] = config.encrypted
            options["trusted_certificates"] = config.trusted_certificates

        # Ignore the type error because the workaround would be duplicating code
        self.driver = GraphDatabase.driver(
            scheme + "://" + hostname,
            **options,  # type: ignore[arg-type]
        )
        # neomodel created this driver and is responsible for closing it.
        self._owns_driver = True
        # Keep the credential-bearing URL private (for reconnection) and expose
        # only a password-redacted version through the public ``url`` attribute.
        self._connection_url = url
        self.url = self._redact_url_password(url)
        # The database name can be provided through the url or the config
        if database_name == "":
            if hasattr(config, "database_name") and config.database_name:
                self._database_name = config.database_name
        else:
            self._database_name = database_name

    def close_connection(self) -> None:
        """
        Closes the currently open driver.
        The driver should always be closed at the end of the application's lifecyle.

        The driver is process-wide, so this closes it for every thread and context. The context-local target database name is reset for the calling
        context only.
        """
        self._database_version = None
        self._database_edition = None
        self._database_name = None
        self._connection_url = None
        if self.driver is not None:
            self.driver.close()
            self.driver = None
        self._owns_driver = False

    @property
    def database_version(self) -> str | None:
        if self._database_version is None:
            self._update_database_version()

        return self._database_version

    @property
    def database_edition(self) -> str | None:
        if self._database_edition is None:
            self._update_database_version()

        return self._database_edition

    @ensure_connection
    def begin(
        self,
        access_mode: str | None = ACCESS_MODE_WRITE,
        timeout: float | None = None,
        **parameters: Any,
    ) -> None:
        """
        Begins a new transaction. Raises SystemError if a transaction is already active.

        :param access_mode: The access mode of the transaction, defaults to write.
        :type access_mode: str
        :param timeout: Transaction timeout in seconds. Falls back to
            config.transaction_timeout when None. Pass 0 to disable the timeout
            for this transaction (the driver will use the server default).
        :type timeout: float | None
        """
        if (
            hasattr(self, "_active_transaction")
            and self._active_transaction is not None
        ):
            raise SystemError("Transaction in progress")

        if self.driver is None:
            raise RuntimeError("Driver has not been created")

        # ``access_mode`` may be None (transaction proxies use it to mean
        # "unspecified"); the driver expects a concrete mode, so default to WRITE.
        self._session = self.driver.session(
            default_access_mode=access_mode or ACCESS_MODE_WRITE,
            database=self._database_name,
            impersonated_user=self.impersonated_user,
            **parameters,
        )

        timeout = get_config().transaction_timeout if timeout is None else timeout
        self._active_transaction = self._session.begin_transaction(timeout=timeout)

    @ensure_connection
    def commit(self) -> Bookmarks:
        """
        Commits the current transaction and closes its session

        :return: last_bookmarks
        """
        if self._active_transaction is None:
            raise RuntimeError(NO_TRANSACTION_IN_PROGRESS)
        if self._session is None:
            raise RuntimeError(NO_SESSION_OPEN)
        try:
            self._active_transaction.commit()
            last_bookmarks: Bookmarks = self._session.last_bookmarks()
        finally:
            # Always release the transaction and session, even if committing
            # above failed. Guard with explicit None-checks (rather than
            # asserts) so cleanup never masks the original error and does not
            # vanish under `python -O`.
            if self._active_transaction is not None:
                self._active_transaction.close()
            if self._session is not None:
                self._session.close()

            self._active_transaction = None
            self._session = None

        return last_bookmarks

    @ensure_connection
    def rollback(self) -> None:
        """
        Rolls back the current transaction and closes its session
        """
        if self._active_transaction is None:
            raise RuntimeError(NO_TRANSACTION_IN_PROGRESS)
        try:
            self._active_transaction.rollback()
        finally:
            # See commit(): guard cleanup with explicit None-checks so it cannot
            # mask the original error or vanish under `python -O`.
            if self._active_transaction is not None:
                self._active_transaction.close()
            if self._session is not None:
                self._session.close()

            self._active_transaction = None
            self._session = None

    def _update_database_version(self) -> None:
        """
        Updates the database server information when it is required
        """
        if self._query is None:
            raise RuntimeError(
                "Query runner has not been wired up; the connection manager must "
                "be owned by a Database instance before use."
            )
        try:
            results = self._query.cypher_query(
                "CALL dbms.components() yield versions, edition return versions[0], edition"
            )
            self._database_version = results[0][0][0]
            self._database_edition = results[0][0][1]
        except ServiceUnavailable:
            # The database server is not running yet
            pass

    def get_id_method(self) -> str:
        db_version = self.database_version
        if db_version is None:
            raise RuntimeError(UNKNOWN_SERVER_VERSION)
        if db_version.startswith(VERSION_LEGACY_ID):
            return LEGACY_ID_METHOD
        else:
            return ELEMENT_ID_METHOD

    def parse_element_id(self, element_id: str | None) -> str | int:
        if element_id is None:
            raise ValueError(
                "Unable to parse element id, are you sure this element has been saved ?"
            )
        db_version = self.database_version
        if db_version is None:
            raise RuntimeError(UNKNOWN_SERVER_VERSION)
        return (
            int(element_id) if db_version.startswith(VERSION_LEGACY_ID) else element_id
        )

    @ensure_connection
    def version_is_higher_than(self, version_tag: str) -> bool:
        """Returns true if the database version is higher or equal to a given tag

        Args:
            version_tag (str): The version to compare against

        Returns:
            bool: True if the database version is higher or equal to the given version
        """
        db_version = self.database_version
        if db_version is None:
            raise RuntimeError(UNKNOWN_SERVER_VERSION)
        return version_tag_to_integer(db_version) >= version_tag_to_integer(version_tag)

    @ensure_connection
    def edition_is_enterprise(self) -> bool:
        """Returns true if the database edition is enterprise

        Returns:
            bool: True if the database edition is enterprise
        """
        edition = self.database_edition
        if edition is None:
            raise RuntimeError(UNKNOWN_SERVER_VERSION)
        return edition == ENTERPRISE_EDITION_TAG

    @ensure_connection
    def parallel_runtime_available(self) -> bool:
        """Returns true if the database supports parallel runtime

        Returns:
            bool: True if the database supports parallel runtime
        """
        return (
            self.version_is_higher_than(VERSION_PARALLEL_RUNTIME_SUPPORT)
            and self.edition_is_enterprise()
        )
