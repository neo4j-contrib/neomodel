"""
Database connection and management for the neomodel module.
"""

import logging
import os
import sys
import time
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, Callable, Iterator, TextIO
from urllib.parse import quote, unquote, urlparse

from neo4j import (
    DEFAULT_DATABASE,
    Driver,
    GraphDatabase,
    Result,
    Session,
    Transaction,
    basic_auth,
)
from neo4j.api import Bookmarks
from neo4j.exceptions import ClientError, ServiceUnavailable, SessionExpired
from neo4j.graph import Node, Path, Relationship

from neomodel.config import get_config
from neomodel.constants import (
    ACCESS_MODE_READ,
    ACCESS_MODE_WRITE,
    CONSTRAINT_ALREADY_EXISTS,
    DROP_CONSTRAINT_COMMAND,
    DROP_INDEX_COMMAND,
    ELEMENT_ID_METHOD,
    ENTERPRISE_EDITION_TAG,
    INDEX_ALREADY_EXISTS,
    LEGACY_ID_METHOD,
    LIST_CONSTRAINTS_COMMAND,
    LOOKUP_INDEX_TYPE,
    NO_SESSION_OPEN,
    NO_TRANSACTION_IN_PROGRESS,
    RULE_ALREADY_EXISTS,
    UNKNOWN_SERVER_VERSION,
    VERSION_FULLTEXT_INDEXES_SUPPORT,
    VERSION_LEGACY_ID,
    VERSION_PARALLEL_RUNTIME_SUPPORT,
    VERSION_RELATIONSHIP_CONSTRAINTS_SUPPORT,
    VERSION_RELATIONSHIP_VECTOR_INDEXES_SUPPORT,
    VERSION_VECTOR_INDEXES_SUPPORT,
)
from neomodel.exceptions import (
    ConstraintValidationFailed,
    FeatureNotSupported,
    NodeClassNotDefined,
    RelationshipClassNotDefined,
    UniqueProperty,
)
from neomodel.properties import FulltextIndex, Property, VectorIndex
from neomodel.util import version_tag_to_integer

# The imports inside this block are only for type checking tools (like mypy or IDEs) to help with code hints and error checking.
# These imports are ignored when the code actually runs, so they don't affect runtime performance or cause circular import problems.
if TYPE_CHECKING:
    from neomodel.sync_.node import StructuredNode  # type: ignore
    from neomodel.sync_.transaction import ImpersonationHandler, TransactionProxy

logger = logging.getLogger(__name__)


def ensure_connection(func: Callable) -> Callable:
    """Decorator that ensures a connection is established before executing the decorated function.

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
            config = get_config()
            if hasattr(config, "database_url") and config.database_url:
                _db.set_connection(url=config.database_url)
            elif hasattr(config, "driver") and config.driver:
                _db.set_connection(driver=config.driver)

        return func(self, *args, **kwargs)

    return wrapper


class Database:
    """
    A singleton object via which all operations from neomodel to the Neo4j backend are handled with.

    This class enforces singleton behavior - only one instance can exist at a time.
    The singleton instance is accessible via the module-level 'db' variable.
    """

    # Shared global registries
    _NODE_CLASS_REGISTRY: dict[frozenset, Any] = {}
    _DB_SPECIFIC_CLASS_REGISTRY: dict[str, dict[frozenset, Any]] = {}

    # Singleton instance tracking
    _instance: "Database | None" = None
    _initialized: bool = False

    def __new__(cls) -> "Database":
        """
        Enforce singleton pattern - only one instance can exist.

        Returns:
            Database: The singleton instance

        Raises:
            RuntimeError: If attempting to create a second instance
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        # Prevent re-initialization of the singleton instance
        if Database._initialized:
            return
        # Private to instances and contexts
        self.__active_transaction: ContextVar[Transaction | None] = ContextVar(
            "_active_transaction", default=None
        )
        self.__url: ContextVar[str | None] = ContextVar("url", default=None)
        self.__driver: ContextVar[Driver | None] = ContextVar("driver", default=None)
        self.__session: ContextVar[Session | None] = ContextVar(
            "_session", default=None
        )
        self.__pid: ContextVar[int | None] = ContextVar("_pid", default=None)
        self.__database_name: ContextVar[str | None] = ContextVar(
            "_database_name", default=DEFAULT_DATABASE
        )
        self.__database_version: ContextVar[str | None] = ContextVar(
            "_database_version", default=None
        )
        self.__database_edition: ContextVar[str | None] = ContextVar(
            "_database_edition", default=None
        )
        self.__impersonated_user: ContextVar[str | None] = ContextVar(
            "impersonated_user", default=None
        )
        self.__parallel_runtime: ContextVar[bool | None] = ContextVar(
            "_parallel_runtime", default=False
        )

        # Mark the singleton as initialized
        Database._initialized = True

    @classmethod
    def get_instance(cls) -> "Database":
        """
        Get the singleton instance of Database.

        Returns:
            Database: The singleton instance
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """
        Reset the singleton instance. This should only be used for testing purposes.

        Warning: This will close any existing connections and reset all state.
        """
        if cls._instance is not None:
            # Close any existing connections
            cls._instance.close_connection()

        cls._instance = None
        cls._initialized = False

    @property
    def _active_transaction(self) -> Transaction | None:
        return self.__active_transaction.get()

    @_active_transaction.setter
    def _active_transaction(self, value: Transaction | None) -> None:
        self.__active_transaction.set(value)

    @property
    def url(self) -> str | None:
        return self.__url.get()

    @url.setter
    def url(self, value: str | None) -> None:
        self.__url.set(value)

    @property
    def driver(self) -> Driver | None:
        return self.__driver.get()

    @driver.setter
    def driver(self, value: Driver | None) -> None:
        self.__driver.set(value)

    @property
    def _session(self) -> Session | None:
        return self.__session.get()

    @_session.setter
    def _session(self, value: Session | None) -> None:
        self.__session.set(value)

    @property
    def _pid(self) -> int | None:
        return self.__pid.get()

    @_pid.setter
    def _pid(self, value: int | None) -> None:
        self.__pid.set(value)

    @property
    def _database_name(self) -> str | None:
        return self.__database_name.get()

    @_database_name.setter
    def _database_name(self, value: str | None) -> None:
        self.__database_name.set(value)

    @property
    def _database_version(self) -> str | None:
        return self.__database_version.get()

    @_database_version.setter
    def _database_version(self, value: str | None) -> None:
        self.__database_version.set(value)

    @property
    def _database_edition(self) -> str | None:
        return self.__database_edition.get()

    @_database_edition.setter
    def _database_edition(self, value: str | None) -> None:
        self.__database_edition.set(value)

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

    def set_connection(
        self, url: str | None = None, driver: Driver | None = None
    ) -> None:
        """
        Sets the connection up and relevant internal. This can be done using a Neo4j URL or a driver instance.

        Args:
            url (str): Optionally, Neo4j URL in the form protocol://username:password@hostname:port/dbname.
            When provided, a Neo4j driver instance will be created by neomodel.

            driver (neo4j.Driver): Optionally, a pre-created driver instance.
            When provided, neomodel will not create a driver instance but use this one instead.
        """
        if driver:
            self.driver = driver
            config = get_config()
            if hasattr(config, "database_name") and config.database_name:
                self._database_name = config.database_name
        elif url:
            self._parse_driver_from_url(url=url)

        self._pid = os.getpid()
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
        p_start = url.replace(":", "", 1).find(":") + 2
        p_end = url.rfind("@")
        password = url[p_start:p_end]
        url = url.replace(password, quote(password))
        parsed_url = urlparse(url)

        valid_schemas = [
            "bolt",
            "bolt+s",
            "bolt+ssc",
            "bolt+routing",
            "neo4j",
            "neo4j+s",
            "neo4j+ssc",
        ]

        if parsed_url.netloc.find("@") > -1 and parsed_url.scheme in valid_schemas:
            credentials, hostname = parsed_url.netloc.rsplit("@", 1)
            username, password = credentials.split(":")
            password = unquote(password)
            database_name = parsed_url.path.strip("/")
        else:
            raise ValueError(
                f"Expecting url format: bolt://user:password@localhost:7687 got {url}"
            )

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

        if "+s" not in parsed_url.scheme:
            options["encrypted"] = config.encrypted
            options["trusted_certificates"] = config.trusted_certificates

        # Ignore the type error because the workaround would be duplicating code
        self.driver = GraphDatabase.driver(
            parsed_url.scheme + "://" + hostname,
            **options,  # type: ignore[arg-type]
        )
        self.url = url
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
        """
        self._database_version = None
        self._database_edition = None
        self._database_name = None
        if self.driver is not None:
            self.driver.close()
            self.driver = None

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

    @property
    def transaction(self) -> "TransactionProxy":
        """
        Returns the current transaction object
        """
        from neomodel.sync_.transaction import TransactionProxy  # type: ignore

        return TransactionProxy(self)

    @property
    def write_transaction(self) -> "TransactionProxy":
        from neomodel.sync_.transaction import TransactionProxy  # type: ignore

        return TransactionProxy(self, access_mode=ACCESS_MODE_WRITE)

    @property
    def read_transaction(self) -> "TransactionProxy":
        from neomodel.sync_.transaction import TransactionProxy  # type: ignore

        return TransactionProxy(self, access_mode=ACCESS_MODE_READ)

    @property
    def parallel_read_transaction(self) -> "TransactionProxy":
        from neomodel.sync_.transaction import TransactionProxy  # type: ignore

        return TransactionProxy(
            self, access_mode=ACCESS_MODE_READ, parallel_runtime=True
        )

    def impersonate(self, user: str) -> "ImpersonationHandler":
        """All queries executed within this context manager will be executed as impersonated user

        Args:
            user (str): User to impersonate

        Returns:
            ImpersonationHandler: Context manager to set/unset the user to impersonate
        """
        from neomodel.sync_.transaction import ImpersonationHandler  # type: ignore

        db_edition = self.database_edition
        if db_edition != ENTERPRISE_EDITION_TAG:
            raise FeatureNotSupported(
                "Impersonation is only available in Neo4j Enterprise edition"
            )
        return ImpersonationHandler(self, impersonated_user=user)

    @ensure_connection
    def begin(self, access_mode: str = ACCESS_MODE_WRITE, **parameters: Any) -> None:
        """
        Begins a new transaction. Raises SystemError if a transaction is already active.
        """
        if (
            hasattr(self, "_active_transaction")
            and self._active_transaction is not None
        ):
            raise SystemError("Transaction in progress")

        assert self.driver is not None, "Driver has not been created"

        self._session = self.driver.session(
            default_access_mode=access_mode,
            database=self._database_name,
            impersonated_user=self.impersonated_user,
            **parameters,
        )

        assert self._session is not None, "Session has not been created"
        self._active_transaction = self._session.begin_transaction()

    @ensure_connection
    def commit(self) -> Bookmarks:
        """
        Commits the current transaction and closes its session

        :return: last_bookmarks
        """
        try:
            assert self._active_transaction is not None, NO_TRANSACTION_IN_PROGRESS
            self._active_transaction.commit()

            assert self._session is not None, NO_SESSION_OPEN
            last_bookmarks: Bookmarks = self._session.last_bookmarks()
        finally:
            # In case something went wrong during
            # committing changes to the database
            # we have to close an active transaction and session.
            assert self._active_transaction is not None, NO_TRANSACTION_IN_PROGRESS
            self._active_transaction.close()

            assert self._session is not None, NO_SESSION_OPEN
            self._session.close()

            self._active_transaction = None
            self._session = None

        return last_bookmarks

    @ensure_connection
    def rollback(self) -> None:
        """
        Rolls back the current transaction and closes its session
        """
        try:
            assert self._active_transaction is not None, NO_TRANSACTION_IN_PROGRESS
            self._active_transaction.rollback()
        finally:
            # In case when something went wrong during changes rollback,
            # we have to close an active transaction and session
            assert self._active_transaction is not None, NO_TRANSACTION_IN_PROGRESS
            self._active_transaction.close()

            assert self._session is not None, NO_SESSION_OPEN
            self._session.close()

            self._active_transaction = None
            self._session = None

    def _update_database_version(self) -> None:
        """
        Updates the database server information when it is required
        """
        try:
            results = self.cypher_query(
                "CALL dbms.components() yield versions, edition return versions[0], edition"
            )
            self._database_version = results[0][0][0]
            self._database_edition = results[0][0][1]
        except ServiceUnavailable:
            # The database server is not running yet
            pass

    def _object_resolution(self, object_to_resolve: Any) -> Any:
        """
        Performs in place automatic object resolution on a result
        returned by cypher_query.

        The function operates recursively in order to be able to resolve Nodes
        within nested list structures and Path objects. Not meant to be called
        directly, used primarily by _result_resolution.

        :param object_to_resolve: A result as returned by cypher_query.
        :type Any:

        :return: An instantiated object.
        """
        # Below is the original comment that came with the code extracted in
        # this method. It is not very clear but I decided to keep it just in
        # case
        #
        #
        # For some reason, while the type of `a_result_attribute[1]`
        # as reported by the neo4j driver is `Node` for Node-type data
        # retrieved from the database.
        # When the retrieved data are Relationship-Type,
        # the returned type is `abc.[REL_LABEL]` which is however
        # a descendant of Relationship.
        # Consequently, the type checking was changed for both
        # Node, Relationship objects
        if isinstance(object_to_resolve, Node):
            _labels = frozenset(object_to_resolve.labels)
            if _labels in self._NODE_CLASS_REGISTRY:
                return self._NODE_CLASS_REGISTRY[_labels].inflate(object_to_resolve)
            elif (
                self._database_name is not None
                and self._database_name in self._DB_SPECIFIC_CLASS_REGISTRY
                and _labels in self._DB_SPECIFIC_CLASS_REGISTRY[self._database_name]
            ):
                return self._DB_SPECIFIC_CLASS_REGISTRY[self._database_name][
                    _labels
                ].inflate(object_to_resolve)
            else:
                raise NodeClassNotDefined(
                    object_to_resolve,
                    self._NODE_CLASS_REGISTRY,
                    self._DB_SPECIFIC_CLASS_REGISTRY,
                )

        if isinstance(object_to_resolve, Relationship):
            rel_type = frozenset([object_to_resolve.type])
            if rel_type in self._NODE_CLASS_REGISTRY:
                return self._NODE_CLASS_REGISTRY[rel_type].inflate(object_to_resolve)
            elif (
                self._database_name is not None
                and self._database_name in self._DB_SPECIFIC_CLASS_REGISTRY
                and rel_type in self._DB_SPECIFIC_CLASS_REGISTRY[self._database_name]
            ):
                return self._DB_SPECIFIC_CLASS_REGISTRY[self._database_name][
                    rel_type
                ].inflate(object_to_resolve)
            else:
                raise RelationshipClassNotDefined(
                    object_to_resolve,
                    self._NODE_CLASS_REGISTRY,
                    self._DB_SPECIFIC_CLASS_REGISTRY,
                )

        if isinstance(object_to_resolve, Path):
            from neomodel.sync_.path import NeomodelPath  # type: ignore

            return NeomodelPath(object_to_resolve)

        if isinstance(object_to_resolve, list):
            return [self._object_resolution(item) for item in object_to_resolve]

        if isinstance(object_to_resolve, dict):
            return {
                key: self._object_resolution(value)
                for key, value in object_to_resolve.items()
            }

        return object_to_resolve

    def _result_resolution(self, result_list: list) -> list:
        """
        Performs in place automatic object resolution on a set of results
        returned by cypher_query.

        The function operates recursively in order to be able to resolve Nodes
        within nested list structures. Not meant to be called directly,
        used primarily by cypher_query.

        :param result_list: A list of results as returned by cypher_query.
        :type list:

        :return: A list of instantiated objects.
        """

        # Object resolution occurs in-place
        for a_result_item in enumerate(result_list):
            for a_result_attribute in enumerate(a_result_item[1]):
                # Primitive types should remain primitive types,
                # Nodes to be resolved to native objects
                resolved_object = a_result_attribute[1]

                resolved_object = self._object_resolution(resolved_object)

                result_list[a_result_item[0]][a_result_attribute[0]] = resolved_object

        return result_list

    @ensure_connection
    def cypher_query(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        handle_unique: bool = True,
        retry_on_session_expire: bool = False,
        resolve_objects: bool = False,
    ) -> tuple[list | None, tuple[str, ...] | None]:
        """
        Runs a query on the database and returns a list of results and their headers.

        :param query: A CYPHER query
        :type: str
        :param params: Dictionary of parameters
        :type: dict
        :param handle_unique: Whether or not to raise UniqueProperty exception on Cypher's ConstraintValidation errors
        :type: bool
        :param retry_on_session_expire: Whether or not to attempt the same query again if the transaction has expired.
        If you use neomodel with your own driver, you must catch SessionExpired exceptions yourself and retry with a new driver instance.
        :type: bool
        :param resolve_objects: Whether to attempt to resolve the returned nodes to data model objects automatically
        :type: bool

        :return: A tuple containing a list of results and a tuple of headers.
        """
        if params is None:
            params = {}
        if self._active_transaction:
            # Use current transaction if a transaction is currently active
            results, meta = self._run_cypher_query(
                self._active_transaction,
                query,
                params,
                handle_unique,
                retry_on_session_expire,
                resolve_objects,
            )
        else:
            # Otherwise create a new session in a with to dispose of it after it has been run
            if self.driver:
                with self.driver.session(
                    database=self._database_name,
                    impersonated_user=self.impersonated_user,
                ) as session:
                    results, meta = self._run_cypher_query(
                        session,
                        query,
                        params,
                        handle_unique,
                        retry_on_session_expire,
                        resolve_objects,
                    )
            else:
                raise ValueError("No driver has been set")

        return results, meta

    def _run_cypher_query(
        self,
        session: Session | Transaction,
        query: str,
        params: dict[str, Any],
        handle_unique: bool,
        retry_on_session_expire: bool,
        resolve_objects: bool,
    ) -> tuple[list | None, tuple[str, ...] | None]:
        try:
            # Retrieve the data
            start = time.time()
            if self._parallel_runtime:
                query = "CYPHER runtime=parallel " + query
            response: Result = session.run(query=query, parameters=params)
            results, meta = [list(r.values()) for r in response], response.keys()
            end = time.time()

            if resolve_objects:
                # Do any automatic resolution required
                results = self._result_resolution(results)

        except ClientError as e:
            if e.code == "Neo.ClientError.Schema.ConstraintValidationFailed":
                if hasattr(e, "message") and e.message is not None:
                    if "already exists with label" in e.message and handle_unique:
                        raise UniqueProperty(e.message) from e
                    raise ConstraintValidationFailed(e.message) from e
                raise ConstraintValidationFailed(
                    "A constraint validation failed"
                ) from e

            exc_info = sys.exc_info()
            if exc_info[1] is not None and exc_info[2] is not None:
                raise exc_info[1].with_traceback(exc_info[2])
        except SessionExpired:
            if retry_on_session_expire:
                self.set_connection(url=self.url)
                return self.cypher_query(
                    query=query,
                    params=params,
                    handle_unique=handle_unique,
                    retry_on_session_expire=False,
                )
            raise

        tte = end - start
        if os.environ.get("NEOMODEL_CYPHER_DEBUG", False) and tte > float(
            os.environ.get("NEOMODEL_SLOW_QUERIES", 0)
        ):
            logger.debug(
                "query: "
                + query
                + "\nparams: "
                + repr(params)
                + f"\ntook: {tte:.2g}s\n"
            )

        return results, meta

    def _stream_cypher_query(
        self,
        session: Session | Transaction,
        query: str,
        params: dict[str, Any],
        handle_unique: bool,
        resolve_objects: bool,
    ) -> Iterator[tuple[list, tuple[str, ...]]]:
        """
        Stream query results one record at a time without loading all into memory.

        This is an internal method used for iteration. It yields results
        as they arrive from the database instead of collecting them all first.

        :param session: Neo4j session or transaction
        :param query: Cypher query string
        :param params: Query parameters
        :param handle_unique: Whether to raise UniqueProperty on constraint violations
        :param resolve_objects: Whether to resolve nodes to neomodel objects
        :yields: Tuple of (values_list, keys_tuple) for each record
        """
        try:
            start = time.time()
            if self._parallel_runtime:
                query = "CYPHER runtime=parallel " + query

            response: Result = session.run(query=query, parameters=params)
            keys = response.keys()

            # Stream results one record at a time
            for record in response:
                values = list(record.values())

                if resolve_objects:
                    # Resolve objects for this single record
                    for idx, value in enumerate(values):
                        values[idx] = self._object_resolution(value)

                yield values, keys

            end = time.time()
            tte = end - start
            if os.environ.get("NEOMODEL_CYPHER_DEBUG", False) and tte > float(
                os.environ.get("NEOMODEL_SLOW_QUERIES", 0)
            ):
                logger.debug(
                    "query: "
                    + query
                    + "\nparams: "
                    + repr(params)
                    + f"\ntook: {tte:.2g}s\n"
                )

        except ClientError as e:
            if e.code == "Neo.ClientError.Schema.ConstraintValidationFailed":
                if hasattr(e, "message") and e.message is not None:
                    if "already exists with label" in e.message and handle_unique:
                        raise UniqueProperty(e.message) from e
                    raise ConstraintValidationFailed(e.message) from e
                raise ConstraintValidationFailed(
                    "A constraint validation failed"
                ) from e

            exc_info = sys.exc_info()
            if exc_info[1] is not None and exc_info[2] is not None:
                raise exc_info[1].with_traceback(exc_info[2])

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

    def list_indexes(self, exclude_token_lookup: bool = False) -> list[dict]:
        """Returns all indexes existing in the database

        Arguments:
            exclude_token_lookup[bool]: Exclude automatically create token lookup indexes

        Returns:
            Sequence[dict]: List of dictionaries, each entry being an index definition
        """
        indexes, meta_indexes = self.cypher_query("SHOW INDEXES")
        indexes_as_dict = [dict(zip(meta_indexes, row)) for row in indexes]

        if exclude_token_lookup:
            indexes_as_dict = [
                obj for obj in indexes_as_dict if obj["type"] != LOOKUP_INDEX_TYPE
            ]

        return indexes_as_dict

    def list_constraints(self) -> list[dict]:
        """Returns all constraints existing in the database

        Returns:
            Sequence[dict]: List of dictionaries, each entry being a constraint definition
        """
        constraints, meta_constraints = self.cypher_query(LIST_CONSTRAINTS_COMMAND)
        constraints_as_dict = [dict(zip(meta_constraints, row)) for row in constraints]

        return constraints_as_dict

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

    def change_neo4j_password(self, user: str, new_password: str) -> None:
        self.cypher_query(f"ALTER USER {user} SET PASSWORD '{new_password}'")

    def clear_neo4j_database(
        self, clear_constraints: bool = False, clear_indexes: bool = False
    ) -> None:
        self.cypher_query(
            """
            MATCH (a)
            CALL { WITH a DETACH DELETE a }
            IN TRANSACTIONS OF 5000 rows
        """
        )
        if clear_constraints:
            self.drop_constraints()
        if clear_indexes:
            self.drop_indexes()

    def drop_constraints(
        self, quiet: bool = True, stdout: TextIO | None = None
    ) -> None:
        """
        Discover and drop all constraints.

        :type: bool
        :return: None
        """
        if not stdout or stdout is None:
            stdout = sys.stdout

        results, meta = self.cypher_query(LIST_CONSTRAINTS_COMMAND)

        results_as_dict = [dict(zip(meta, row)) for row in results]
        for constraint in results_as_dict:
            self.cypher_query(DROP_CONSTRAINT_COMMAND + constraint["name"])
            if not quiet:
                stdout.write(
                    (
                        " - Dropping unique constraint and index"
                        f" on label {constraint['labelsOrTypes'][0]}"
                        f" with property {constraint['properties'][0]}.\n"
                    )
                )
        if not quiet:
            stdout.write("\n")

    def drop_indexes(self, quiet: bool = True, stdout: TextIO | None = None) -> None:
        """
        Discover and drop all indexes, except the automatically created token lookup indexes.

        :type: bool
        :return: None
        """
        if not stdout or stdout is None:
            stdout = sys.stdout

        indexes = self.list_indexes(exclude_token_lookup=True)
        for index in indexes:
            self.cypher_query(DROP_INDEX_COMMAND + index["name"])
            if not quiet:
                stdout.write(
                    f" - Dropping index on labels {','.join(index['labelsOrTypes'])} with properties {','.join(index['properties'])}.\n"
                )
        if not quiet:
            stdout.write("\n")

    def remove_all_labels(self, stdout: TextIO | None = None) -> None:
        """
        Calls functions for dropping constraints and indexes.

        :param stdout: output stream
        :return: None
        """

        if not stdout:
            stdout = sys.stdout

        stdout.write("Dropping constraints...\n")
        self.drop_constraints(quiet=False, stdout=stdout)

        stdout.write("Dropping indexes...\n")
        self.drop_indexes(quiet=False, stdout=stdout)

    def install_all_labels(self, stdout: TextIO | None = None) -> None:
        """
        Discover all subclasses of StructuredNode in your application and execute install_labels on each.
        Note: code must be loaded (imported) in order for a class to be discovered.

        :param stdout: output stream
        :return: None
        """

        if not stdout or stdout is None:
            stdout = sys.stdout

        def subsub(cls: Any) -> list:  # recursively return all subclasses
            subclasses = cls.__subclasses__()
            if not subclasses:  # base case: no more subclasses
                return []
            return subclasses + [g for s in cls.__subclasses__() for g in subsub(s)]

        stdout.write("Setting up indexes and constraints...\n\n")

        i = 0
        from .node import StructuredNode

        for cls in subsub(StructuredNode):
            stdout.write(f"Found {cls.__module__}.{cls.__name__}\n")
            self.install_labels(cls, quiet=False, stdout=stdout)
            i += 1

        if i:
            stdout.write("\n")

        stdout.write(f"Finished {i} classes.\n")

    def install_labels(
        self, cls: Any, quiet: bool = True, stdout: TextIO | None = None
    ) -> None:
        """
        Setup labels with indexes and constraints for a given class

        :param cls: StructuredNode class
        :type: class
        :param quiet: (default true) enable standard output
        :param stdout: stdout stream
        :type: bool
        :return: None
        """
        _stdout = stdout if stdout else sys.stdout

        if not hasattr(cls, "__label__"):
            if not quiet:
                _stdout.write(
                    f" ! Skipping class {cls.__module__}.{cls.__name__} is abstract\n"
                )
            return

        for name, property in cls.defined_properties(aliases=False, rels=False).items():
            self._install_node(cls, name, property, quiet, _stdout)

        for _, relationship in cls.defined_properties(
            aliases=False, rels=True, properties=False
        ).items():
            self._install_relationship(cls, relationship, quiet, _stdout)

    def _create_node_index(
        self, target_cls: Any, property_name: str, stdout: TextIO, quiet: bool
    ) -> None:
        label = target_cls.__label__
        index_name = f"index_{label}_{property_name}"
        if not quiet:
            stdout.write(
                f" + Creating node index for {property_name} on label {label} for class {target_cls.__module__}.{target_cls.__name__}\n"
            )
        try:
            self.cypher_query(
                f"CREATE INDEX {index_name} FOR (n:{label}) ON (n.{property_name}); "
            )
        except ClientError as e:
            if e.code in (
                RULE_ALREADY_EXISTS,
                INDEX_ALREADY_EXISTS,
            ):
                stdout.write(f"{str(e)}\n")
            else:
                raise

    def _create_node_fulltext_index(
        self,
        target_cls: Any,
        property_name: str,
        stdout: TextIO,
        fulltext_index: FulltextIndex,
        quiet: bool,
    ) -> None:
        if self.version_is_higher_than(VERSION_FULLTEXT_INDEXES_SUPPORT):
            label = target_cls.__label__
            index_name = f"fulltext_index_{label}_{property_name}"
            if not quiet:
                stdout.write(
                    f" + Creating fulltext index for {property_name} on label {target_cls.__label__} for class {target_cls.__module__}.{target_cls.__name__}\n"
                )
            query = f"""
                CREATE FULLTEXT INDEX {index_name} FOR (n:{label}) ON EACH [n.{property_name}]
                OPTIONS {{
                    indexConfig: {{
                        `fulltext.analyzer`: '{fulltext_index.analyzer}',
                        `fulltext.eventually_consistent`: {fulltext_index.eventually_consistent}
                    }}
                }};
            """
            try:
                self.cypher_query(query)
            except ClientError as e:
                if e.code in (
                    RULE_ALREADY_EXISTS,
                    INDEX_ALREADY_EXISTS,
                ):
                    stdout.write(f"{str(e)}\n")
                else:
                    raise
        else:
            raise FeatureNotSupported(
                f"Creation of full-text indexes from neomodel is not supported for Neo4j in version {self.database_version}. Please upgrade to Neo4j 5.16 or higher."
            )

    def _create_node_vector_index(
        self,
        target_cls: Any,
        property_name: str,
        stdout: TextIO,
        vector_index: VectorIndex,
        quiet: bool,
    ) -> None:
        if self.version_is_higher_than(VERSION_VECTOR_INDEXES_SUPPORT):
            label = target_cls.__label__
            index_name = f"vector_index_{label}_{property_name}"
            if not quiet:
                stdout.write(
                    f" + Creating vector index for {property_name} on label {label} for class {target_cls.__module__}.{target_cls.__name__}\n"
                )
            query = f"""
                CREATE VECTOR INDEX {index_name} FOR (n:{label}) ON n.{property_name}
                OPTIONS {{
                    indexConfig: {{
                        `vector.dimensions`: {vector_index.dimensions},
                        `vector.similarity_function`: '{vector_index.similarity_function}'
                    }}
                }};
            """
            try:
                self.cypher_query(query)
            except ClientError as e:
                if e.code in (
                    RULE_ALREADY_EXISTS,
                    INDEX_ALREADY_EXISTS,
                ):
                    stdout.write(f"{str(e)}\n")
                else:
                    raise
        else:
            raise FeatureNotSupported(
                f"Creation of vector indexes from neomodel is not supported for Neo4j in version {self.database_version}. Please upgrade to Neo4j 5.15 or higher."
            )

    def _create_node_constraint(
        self, target_cls: Any, property_name: str, stdout: TextIO, quiet: bool
    ) -> None:
        label = target_cls.__label__
        constraint_name = f"constraint_unique_{label}_{property_name}"
        if not quiet:
            stdout.write(
                f" + Creating node unique constraint for {property_name} on label {target_cls.__label__} for class {target_cls.__module__}.{target_cls.__name__}\n"
            )
        try:
            self.cypher_query(
                f"""CREATE CONSTRAINT {constraint_name}
                            FOR (n:{label}) REQUIRE n.{property_name} IS UNIQUE"""
            )
        except ClientError as e:
            if e.code in (
                RULE_ALREADY_EXISTS,
                CONSTRAINT_ALREADY_EXISTS,
            ):
                stdout.write(f"{str(e)}\n")
            else:
                raise

    def _create_relationship_index(
        self,
        relationship_type: str,
        target_cls: Any,
        relationship_cls: Any,
        property_name: str,
        stdout: TextIO,
        quiet: bool,
    ) -> None:
        index_name = f"index_{relationship_type}_{property_name}"
        if not quiet:
            stdout.write(
                f" + Creating relationship index for {property_name} on relationship type {relationship_type} for relationship model {target_cls.__module__}.{relationship_cls.__name__}\n"
            )
        try:
            self.cypher_query(
                f"CREATE INDEX {index_name} FOR ()-[r:{relationship_type}]-() ON (r.{property_name}); "
            )
        except ClientError as e:
            if e.code in (
                RULE_ALREADY_EXISTS,
                INDEX_ALREADY_EXISTS,
            ):
                stdout.write(f"{str(e)}\n")
            else:
                raise

    def _create_relationship_fulltext_index(
        self,
        relationship_type: str,
        target_cls: Any,
        relationship_cls: Any,
        property_name: str,
        stdout: TextIO,
        fulltext_index: FulltextIndex,
        quiet: bool,
    ) -> None:
        if self.version_is_higher_than(VERSION_FULLTEXT_INDEXES_SUPPORT):
            index_name = f"fulltext_index_{relationship_type}_{property_name}"
            if not quiet:
                stdout.write(
                    f" + Creating fulltext index for {property_name} on relationship type {relationship_type} for relationship model {target_cls.__module__}.{relationship_cls.__name__}\n"
                )
            query = f"""
                CREATE FULLTEXT INDEX {index_name} FOR ()-[r:{relationship_type}]-() ON EACH [r.{property_name}]
                OPTIONS {{
                    indexConfig: {{
                        `fulltext.analyzer`: '{fulltext_index.analyzer}',
                        `fulltext.eventually_consistent`: {fulltext_index.eventually_consistent}
                    }}
                }};
            """
            try:
                self.cypher_query(query)
            except ClientError as e:
                if e.code in (
                    RULE_ALREADY_EXISTS,
                    INDEX_ALREADY_EXISTS,
                ):
                    stdout.write(f"{str(e)}\n")
                else:
                    raise
        else:
            raise FeatureNotSupported(
                f"Creation of full-text indexes from neomodel is not supported for Neo4j in version {self.database_version}. Please upgrade to Neo4j 5.16 or higher."
            )

    def _create_relationship_vector_index(
        self,
        relationship_type: str,
        target_cls: Any,
        relationship_cls: Any,
        property_name: str,
        stdout: TextIO,
        vector_index: VectorIndex,
        quiet: bool,
    ) -> None:
        if self.version_is_higher_than(VERSION_RELATIONSHIP_VECTOR_INDEXES_SUPPORT):
            index_name = f"vector_index_{relationship_type}_{property_name}"
            if not quiet:
                stdout.write(
                    f" + Creating vector index for {property_name} on relationship type {relationship_type} for relationship model {target_cls.__module__}.{relationship_cls.__name__}\n"
                )
            query = f"""
                CREATE VECTOR INDEX {index_name} FOR ()-[r:{relationship_type}]-() ON r.{property_name}
                OPTIONS {{
                    indexConfig: {{
                        `vector.dimensions`: {vector_index.dimensions},
                        `vector.similarity_function`: '{vector_index.similarity_function}'
                    }}
                }};
            """
            try:
                self.cypher_query(query)
            except ClientError as e:
                if e.code in (
                    RULE_ALREADY_EXISTS,
                    INDEX_ALREADY_EXISTS,
                ):
                    stdout.write(f"{str(e)}\n")
                else:
                    raise
        else:
            raise FeatureNotSupported(
                f"Creation of vector indexes for relationships from neomodel is not supported for Neo4j in version {self.database_version}. Please upgrade to Neo4j 5.18 or higher."
            )

    def _create_relationship_constraint(
        self,
        relationship_type: str,
        target_cls: Any,
        relationship_cls: Any,
        property_name: str,
        stdout: TextIO,
        quiet: bool,
    ) -> None:
        if self.version_is_higher_than(VERSION_RELATIONSHIP_CONSTRAINTS_SUPPORT):
            constraint_name = f"constraint_unique_{relationship_type}_{property_name}"
            if not quiet:
                stdout.write(
                    f" + Creating relationship unique constraint for {property_name} on relationship type {relationship_type} for relationship model {target_cls.__module__}.{relationship_cls.__name__}\n"
                )
            try:
                self.cypher_query(
                    f"""CREATE CONSTRAINT {constraint_name}
                                FOR ()-[r:{relationship_type}]-() REQUIRE r.{property_name} IS UNIQUE"""
                )
            except ClientError as e:
                if e.code in (
                    RULE_ALREADY_EXISTS,
                    CONSTRAINT_ALREADY_EXISTS,
                ):
                    stdout.write(f"{str(e)}\n")
                else:
                    raise
        else:
            raise FeatureNotSupported(
                f"Unique indexes on relationships are not supported in Neo4j version {self.database_version}. Please upgrade to Neo4j 5.7 or higher."
            )

    def _install_node(
        self, cls: Any, name: str, property: Property, quiet: bool, stdout: TextIO
    ) -> None:
        # Create indexes and constraints for node property
        db_property = property.get_db_property_name(name)
        if property.index:
            self._create_node_index(
                target_cls=cls, property_name=db_property, stdout=stdout, quiet=quiet
            )
        elif property.unique_index:
            self._create_node_constraint(
                target_cls=cls, property_name=db_property, stdout=stdout, quiet=quiet
            )

        if property.fulltext_index:
            self._create_node_fulltext_index(
                target_cls=cls,
                property_name=db_property,
                stdout=stdout,
                fulltext_index=property.fulltext_index,
                quiet=quiet,
            )

        if property.vector_index:
            self._create_node_vector_index(
                target_cls=cls,
                property_name=db_property,
                stdout=stdout,
                vector_index=property.vector_index,
                quiet=quiet,
            )

    def _install_relationship(
        self, cls: Any, relationship: Any, quiet: bool, stdout: TextIO
    ) -> None:
        # Create indexes and constraints for relationship property
        relationship_cls = relationship.definition["model"]
        if relationship_cls is not None:
            relationship_type = relationship.definition["relation_type"]
            for prop_name, property in relationship_cls.defined_properties(
                aliases=False, rels=False
            ).items():
                db_property = property.get_db_property_name(prop_name)
                if property.index:
                    self._create_relationship_index(
                        relationship_type=relationship_type,
                        target_cls=cls,
                        relationship_cls=relationship_cls,
                        property_name=db_property,
                        stdout=stdout,
                        quiet=quiet,
                    )
                elif property.unique_index:
                    self._create_relationship_constraint(
                        relationship_type=relationship_type,
                        target_cls=cls,
                        relationship_cls=relationship_cls,
                        property_name=db_property,
                        stdout=stdout,
                        quiet=quiet,
                    )

                if property.fulltext_index:
                    self._create_relationship_fulltext_index(
                        relationship_type=relationship_type,
                        target_cls=cls,
                        relationship_cls=relationship_cls,
                        property_name=db_property,
                        stdout=stdout,
                        fulltext_index=property.fulltext_index,
                        quiet=quiet,
                    )

                if property.vector_index:
                    self._create_relationship_vector_index(
                        relationship_type=relationship_type,
                        target_cls=cls,
                        relationship_cls=relationship_cls,
                        property_name=db_property,
                        stdout=stdout,
                        vector_index=property.vector_index,
                        quiet=quiet,
                    )


# Create a singleton instance of the database object
db = Database.get_instance()
