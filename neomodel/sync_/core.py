import logging
import os
import sys
import time
import warnings
from asyncio import iscoroutinefunction
from functools import wraps
from itertools import combinations
from threading import local
from typing import Any, Callable, Optional, TextIO, Union
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

from neomodel import config
from neomodel._async_compat.util import Util
from neomodel.exceptions import (
    ConstraintValidationFailed,
    DoesNotExist,
    FeatureNotSupported,
    NodeClassAlreadyDefined,
    NodeClassNotDefined,
    RelationshipClassNotDefined,
    UniqueProperty,
)
from neomodel.hooks import hooks
from neomodel.properties import FulltextIndex, Property, VectorIndex
from neomodel.sync_.property_manager import PropertyManager
from neomodel.util import (
    _UnsavedNode,
    classproperty,
    deprecated,
    version_tag_to_integer,
)

logger = logging.getLogger(__name__)

RULE_ALREADY_EXISTS = "Neo.ClientError.Schema.EquivalentSchemaRuleAlreadyExists"
INDEX_ALREADY_EXISTS = "Neo.ClientError.Schema.IndexAlreadyExists"
CONSTRAINT_ALREADY_EXISTS = "Neo.ClientError.Schema.ConstraintAlreadyExists"
STREAMING_WARNING = "streaming is not supported by bolt, please remove the kwarg"
NOT_COROUTINE_ERROR = "The decorated function must be a coroutine"


# make sure the connection url has been set prior to executing the wrapped function
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
            if hasattr(config, "DATABASE_URL") and config.DATABASE_URL:
                _db.set_connection(url=config.DATABASE_URL)
            elif hasattr(config, "DRIVER") and config.DRIVER:
                _db.set_connection(driver=config.DRIVER)

        return func(self, *args, **kwargs)

    return wrapper


class Database(local):
    """
    A singleton object via which all operations from neomodel to the Neo4j backend are handled with.
    """

    _NODE_CLASS_REGISTRY: dict[frozenset, Any] = {}
    _DB_SPECIFIC_CLASS_REGISTRY: dict[str, dict[frozenset, Any]] = {}

    def __init__(self) -> None:
        self._active_transaction: Optional[Transaction] = None
        self.url: Optional[str] = None
        self.driver: Optional[Driver] = None
        self._session: Optional[Session] = None
        self._pid: Optional[int] = None
        self._database_name: Optional[str] = DEFAULT_DATABASE
        self._database_version: Optional[str] = None
        self._database_edition: Optional[str] = None
        self.impersonated_user: Optional[str] = None
        self._parallel_runtime: Optional[bool] = False

    def set_connection(
        self, url: Optional[str] = None, driver: Optional[Driver] = None
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
            if hasattr(config, "DATABASE_NAME") and config.DATABASE_NAME:
                self._database_name = config.DATABASE_NAME
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

        options = {
            "auth": basic_auth(username, password),
            "connection_acquisition_timeout": config.CONNECTION_ACQUISITION_TIMEOUT,
            "connection_timeout": config.CONNECTION_TIMEOUT,
            "keep_alive": config.KEEP_ALIVE,
            "max_connection_lifetime": config.MAX_CONNECTION_LIFETIME,
            "max_connection_pool_size": config.MAX_CONNECTION_POOL_SIZE,
            "max_transaction_retry_time": config.MAX_TRANSACTION_RETRY_TIME,
            "resolver": config.RESOLVER,
            "user_agent": config.USER_AGENT,
        }

        if "+s" not in parsed_url.scheme:
            options["encrypted"] = config.ENCRYPTED
            options["trusted_certificates"] = config.TRUSTED_CERTIFICATES

        # Ignore the type error because the workaround would be duplicating code
        self.driver = GraphDatabase.driver(
            parsed_url.scheme + "://" + hostname, **options  # type: ignore[arg-type]
        )
        self.url = url
        # The database name can be provided through the url or the config
        if database_name == "":
            if hasattr(config, "DATABASE_NAME") and config.DATABASE_NAME:
                self._database_name = config.DATABASE_NAME
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
    def database_version(self) -> Optional[str]:
        if self._database_version is None:
            self._update_database_version()

        return self._database_version

    @property
    def database_edition(self) -> Optional[str]:
        if self._database_edition is None:
            self._update_database_version()

        return self._database_edition

    @property
    def transaction(self) -> "TransactionProxy":
        """
        Returns the current transaction object
        """
        return TransactionProxy(self)

    @property
    def write_transaction(self) -> "TransactionProxy":
        return TransactionProxy(self, access_mode="WRITE")

    @property
    def read_transaction(self) -> "TransactionProxy":
        return TransactionProxy(self, access_mode="READ")

    @property
    def parallel_read_transaction(self) -> "TransactionProxy":
        return TransactionProxy(self, access_mode="READ", parallel_runtime=True)

    def impersonate(self, user: str) -> "ImpersonationHandler":
        """All queries executed within this context manager will be executed as impersonated user

        Args:
            user (str): User to impersonate

        Returns:
            ImpersonationHandler: Context manager to set/unset the user to impersonate
        """
        db_edition = self.database_edition
        if db_edition != "enterprise":
            raise FeatureNotSupported(
                "Impersonation is only available in Neo4j Enterprise edition"
            )
        return ImpersonationHandler(self, impersonated_user=user)

    @ensure_connection
    def begin(self, access_mode: str = "WRITE", **parameters: Any) -> None:
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
            assert self._active_transaction is not None, "No transaction in progress"
            self._active_transaction.commit()

            assert self._session is not None, "No session open"
            last_bookmarks: Bookmarks = self._session.last_bookmarks()
        finally:
            # In case something went wrong during
            # committing changes to the database
            # we have to close an active transaction and session.
            assert self._active_transaction is not None, "No transaction in progress"
            self._active_transaction.close()

            assert self._session is not None, "No session open"
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
            assert self._active_transaction is not None, "No transaction in progress"
            self._active_transaction.rollback()
        finally:
            # In case when something went wrong during changes rollback,
            # we have to close an active transaction and session
            assert self._active_transaction is not None, "No transaction in progress"
            self._active_transaction.close()

            assert self._session is not None, "No session open"
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
            from neomodel.sync_.path import NeomodelPath

            return NeomodelPath(object_to_resolve)

        if isinstance(object_to_resolve, list):
            return self._result_resolution([object_to_resolve])

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
        params: Optional[dict[str, Any]] = None,
        handle_unique: bool = True,
        retry_on_session_expire: bool = False,
        resolve_objects: bool = False,
    ) -> tuple[Optional[list], Optional[tuple[str, ...]]]:
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
        session: Union[Session, Transaction],
        query: str,
        params: dict[str, Any],
        handle_unique: bool,
        retry_on_session_expire: bool,
        resolve_objects: bool,
    ) -> tuple[Optional[list], Optional[tuple[str, ...]]]:
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

    def get_id_method(self) -> str:
        db_version = self.database_version
        if db_version is None:
            raise RuntimeError(
                """
                Unable to perform this operation because the database server version is not known. 
                This might mean that the database server is offline.
                """
            )
        if db_version.startswith("4"):
            return "id"
        else:
            return "elementId"

    def parse_element_id(self, element_id: Optional[str]) -> Union[str, int]:
        if element_id is None:
            raise ValueError(
                "Unable to parse element id, are you sure this element has been saved ?"
            )
        db_version = self.database_version
        if db_version is None:
            raise RuntimeError(
                """
                Unable to perform this operation because the database server version is not known. 
                This might mean that the database server is offline.
                """
            )
        return int(element_id) if db_version.startswith("4") else element_id

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
                obj for obj in indexes_as_dict if obj["type"] != "LOOKUP"
            ]

        return indexes_as_dict

    def list_constraints(self) -> list[dict]:
        """Returns all constraints existing in the database

        Returns:
            Sequence[dict]: List of dictionaries, each entry being a constraint definition
        """
        constraints, meta_constraints = self.cypher_query("SHOW CONSTRAINTS")
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
            raise RuntimeError(
                """
                Unable to perform this operation because the database server version is not known. 
                This might mean that the database server is offline.
                """
            )
        return version_tag_to_integer(db_version) >= version_tag_to_integer(version_tag)

    @ensure_connection
    def edition_is_enterprise(self) -> bool:
        """Returns true if the database edition is enterprise

        Returns:
            bool: True if the database edition is enterprise
        """
        edition = self.database_edition
        if edition is None:
            raise RuntimeError(
                """
                Unable to perform this operation because the database server edition is not known. 
                This might mean that the database server is offline.
                """
            )
        return edition == "enterprise"

    @ensure_connection
    def parallel_runtime_available(self) -> bool:
        """Returns true if the database supports parallel runtime

        Returns:
            bool: True if the database supports parallel runtime
        """
        return self.version_is_higher_than("5.13") and self.edition_is_enterprise()

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
            drop_constraints()
        if clear_indexes:
            drop_indexes()

    def drop_constraints(
        self, quiet: bool = True, stdout: Optional[TextIO] = None
    ) -> None:
        """
        Discover and drop all constraints.

        :type: bool
        :return: None
        """
        if not stdout or stdout is None:
            stdout = sys.stdout

        results, meta = self.cypher_query("SHOW CONSTRAINTS")

        results_as_dict = [dict(zip(meta, row)) for row in results]
        for constraint in results_as_dict:
            self.cypher_query("DROP CONSTRAINT " + constraint["name"])
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

    def drop_indexes(self, quiet: bool = True, stdout: Optional[TextIO] = None) -> None:
        """
        Discover and drop all indexes, except the automatically created token lookup indexes.

        :type: bool
        :return: None
        """
        if not stdout or stdout is None:
            stdout = sys.stdout

        indexes = self.list_indexes(exclude_token_lookup=True)
        for index in indexes:
            self.cypher_query("DROP INDEX " + index["name"])
            if not quiet:
                stdout.write(
                    f' - Dropping index on labels {",".join(index["labelsOrTypes"])} with properties {",".join(index["properties"])}.\n'
                )
        if not quiet:
            stdout.write("\n")

    def remove_all_labels(self, stdout: Optional[TextIO] = None) -> None:
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

    def install_all_labels(self, stdout: Optional[TextIO] = None) -> None:
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
        for cls in subsub(StructuredNode):
            stdout.write(f"Found {cls.__module__}.{cls.__name__}\n")
            install_labels(cls, quiet=False, stdout=stdout)
            i += 1

        if i:
            stdout.write("\n")

        stdout.write(f"Finished {i} classes.\n")

    def install_labels(
        self, cls: Any, quiet: bool = True, stdout: Optional[TextIO] = None
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
        if self.version_is_higher_than("5.16"):
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
        if self.version_is_higher_than("5.15"):
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
        if self.version_is_higher_than("5.16"):
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
        if self.version_is_higher_than("5.18"):
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
        if self.version_is_higher_than("5.7"):
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
db = Database()


# Deprecated methods
def change_neo4j_password(db: Database, user: str, new_password: str) -> None:
    deprecated(
        """
        This method has been moved to the Database singleton (db for sync, db for async).
        Please use db.change_neo4j_password(user, new_password) instead.
        This direct call will be removed in an upcoming version.
        """
    )
    db.change_neo4j_password(user, new_password)


def clear_neo4j_database(
    db: Database, clear_constraints: bool = False, clear_indexes: bool = False
) -> None:
    deprecated(
        """
        This method has been moved to the Database singleton (db for sync, db for async).
        Please use db.clear_neo4j_database(clear_constraints, clear_indexes) instead.
        This direct call will be removed in an upcoming version.
        """
    )
    db.clear_neo4j_database(clear_constraints, clear_indexes)


def drop_constraints(quiet: bool = True, stdout: Optional[TextIO] = None) -> None:
    deprecated(
        """
        This method has been moved to the Database singleton (db for sync, db for async).
        Please use db.drop_constraints(quiet, stdout) instead.
        This direct call will be removed in an upcoming version.
        """
    )
    db.drop_constraints(quiet, stdout)


def drop_indexes(quiet: bool = True, stdout: Optional[TextIO] = None) -> None:
    deprecated(
        """
        This method has been moved to the Database singleton (db for sync, db for async).
        Please use db.drop_indexes(quiet, stdout) instead.
        This direct call will be removed in an upcoming version.
        """
    )
    db.drop_indexes(quiet, stdout)


def remove_all_labels(stdout: Optional[TextIO] = None) -> None:
    deprecated(
        """
        This method has been moved to the Database singleton (db for sync, db for async).
        Please use db.remove_all_labels(stdout) instead.
        This direct call will be removed in an upcoming version.
        """
    )
    db.remove_all_labels(stdout)


def install_labels(
    cls: Any, quiet: bool = True, stdout: Optional[TextIO] = None
) -> None:
    deprecated(
        """
        This method has been moved to the Database singleton (db for sync, db for async).
        Please use db.install_labels(cls, quiet, stdout) instead.
        This direct call will be removed in an upcoming version.
        """
    )
    db.install_labels(cls, quiet, stdout)


def install_all_labels(stdout: Optional[TextIO] = None) -> None:
    deprecated(
        """
        This method has been moved to the Database singleton (db for sync, db for async).
        Please use db.install_all_labels(stdout) instead.
        This direct call will be removed in an upcoming version.
        """
    )
    db.install_all_labels(stdout)


class TransactionProxy:
    bookmarks: Optional[Bookmarks] = None

    def __init__(
        self,
        db: Database,
        access_mode: Optional[str] = None,
        parallel_runtime: Optional[bool] = False,
    ):
        self.db: Database = db
        self.access_mode: Optional[str] = access_mode
        self.parallel_runtime: Optional[bool] = parallel_runtime

    @ensure_connection
    def __enter__(self) -> "TransactionProxy":
        if self.parallel_runtime and not self.db.parallel_runtime_available():
            warnings.warn(
                "Parallel runtime is only available in Neo4j Enterprise Edition 5.13 and above. "
                "Reverting to default runtime.",
                UserWarning,
            )
            self.parallel_runtime = False
        self.db._parallel_runtime = self.parallel_runtime
        self.db.begin(access_mode=self.access_mode, bookmarks=self.bookmarks)
        self.bookmarks = None
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.db._parallel_runtime = False
        if exc_value:
            self.db.rollback()

        if (
            exc_type is ClientError
            and exc_value.code == "Neo.ClientError.Schema.ConstraintValidationFailed"
        ):
            raise UniqueProperty(exc_value.message)

        if not exc_value:
            self.last_bookmark = self.db.commit()

    def __call__(self, func: Callable) -> Callable:
        if Util.is_async_code and not iscoroutinefunction(func):
            raise TypeError(NOT_COROUTINE_ERROR)

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Callable:
            with self:
                return func(*args, **kwargs)

        return wrapper

    @property
    def with_bookmark(self) -> "BookmarkingAsyncTransactionProxy":
        return BookmarkingAsyncTransactionProxy(self.db, self.access_mode)


class BookmarkingAsyncTransactionProxy(TransactionProxy):
    def __call__(self, func: Callable) -> Callable:
        if Util.is_async_code and not iscoroutinefunction(func):
            raise TypeError(NOT_COROUTINE_ERROR)

        def wrapper(*args: Any, **kwargs: Any) -> tuple[Any, None]:
            self.bookmarks = kwargs.pop("bookmarks", None)

            with self:
                result = func(*args, **kwargs)
                self.last_bookmark = None

            return result, self.last_bookmark

        return wrapper


class ImpersonationHandler:
    def __init__(self, db: Database, impersonated_user: str):
        self.db = db
        self.impersonated_user = impersonated_user

    def __enter__(self) -> "ImpersonationHandler":
        self.db.impersonated_user = self.impersonated_user
        return self

    def __exit__(
        self, exception_type: Any, exception_value: Any, exception_traceback: Any
    ) -> None:
        self.db.impersonated_user = None

        print("\nException type:", exception_type)
        print("\nException value:", exception_value)
        print("\nTraceback:", exception_traceback)

    def __call__(self, func: Callable) -> Callable:
        def wrapper(*args: Any, **kwargs: Any) -> Callable:
            with self:
                return func(*args, **kwargs)

        return wrapper


class NodeMeta(type):
    DoesNotExist: type[DoesNotExist]
    __required_properties__: tuple[str, ...]
    __all_properties__: tuple[tuple[str, Any], ...]
    __all_aliases__: tuple[tuple[str, Any], ...]
    __all_relationships__: tuple[tuple[str, Any], ...]
    __label__: str
    __optional_labels__: list[str]

    defined_properties: Callable[..., dict[str, Any]]

    def __new__(
        mcs: type, name: str, bases: tuple[type, ...], namespace: dict[str, Any]
    ) -> Any:
        namespace["DoesNotExist"] = type(name + "DoesNotExist", (DoesNotExist,), {})
        cls: NodeMeta = type.__new__(mcs, name, bases, namespace)
        cls.DoesNotExist._model_class = cls

        if hasattr(cls, "__abstract_node__"):
            delattr(cls, "__abstract_node__")
        else:
            if "deleted" in namespace:
                raise ValueError(
                    "Property name 'deleted' is not allowed as it conflicts with neomodel internals."
                )
            elif "id" in namespace:
                raise ValueError(
                    """
                        Property name 'id' is not allowed as it conflicts with neomodel internals.
                        Consider using 'uid' or 'identifier' as id is also a Neo4j internal.
                    """
                )
            elif "element_id" in namespace:
                raise ValueError(
                    """
                        Property name 'element_id' is not allowed as it conflicts with neomodel internals.
                        Consider using 'uid' or 'identifier' as element_id is also a Neo4j internal.
                    """
                )
            for key, value in (
                (x, y) for x, y in namespace.items() if isinstance(y, Property)
            ):
                value.name, value.owner = key, cls
                if hasattr(value, "setup") and callable(value.setup):
                    value.setup()

            # cache various groups of properies
            cls.__required_properties__ = tuple(
                name
                for name, property in cls.defined_properties(
                    aliases=False, rels=False
                ).items()
                if property.required or property.unique_index
            )
            cls.__all_properties__ = tuple(
                cls.defined_properties(aliases=False, rels=False).items()
            )
            cls.__all_aliases__ = tuple(
                cls.defined_properties(properties=False, rels=False).items()
            )
            cls.__all_relationships__ = tuple(
                cls.defined_properties(aliases=False, properties=False).items()
            )

            cls.__label__ = namespace.get("__label__", name)
            cls.__optional_labels__ = namespace.get("__optional_labels__", [])

            build_class_registry(cls)

        return cls


def build_class_registry(cls: Any) -> None:
    base_label_set = frozenset(cls.inherited_labels())
    optional_label_set = set(cls.inherited_optional_labels())

    # Construct all possible combinations of labels + optional labels
    possible_label_combinations = [
        frozenset(set(x).union(base_label_set))
        for i in range(1, len(optional_label_set) + 1)
        for x in combinations(optional_label_set, i)
    ]
    possible_label_combinations.append(base_label_set)

    for label_set in possible_label_combinations:
        if not hasattr(cls, "__target_databases__"):
            if label_set not in db._NODE_CLASS_REGISTRY:
                db._NODE_CLASS_REGISTRY[label_set] = cls
            else:
                raise NodeClassAlreadyDefined(
                    cls, db._NODE_CLASS_REGISTRY, db._DB_SPECIFIC_CLASS_REGISTRY
                )
        else:
            for database in cls.__target_databases__:
                if database not in db._DB_SPECIFIC_CLASS_REGISTRY:
                    db._DB_SPECIFIC_CLASS_REGISTRY[database] = {}
                if label_set not in db._DB_SPECIFIC_CLASS_REGISTRY[database]:
                    db._DB_SPECIFIC_CLASS_REGISTRY[database][label_set] = cls
                else:
                    raise NodeClassAlreadyDefined(
                        cls, db._NODE_CLASS_REGISTRY, db._DB_SPECIFIC_CLASS_REGISTRY
                    )


NodeBase: type = NodeMeta("NodeBase", (PropertyManager,), {"__abstract_node__": True})


class StructuredNode(NodeBase):
    """
    Base class for all node definitions to inherit from.

    If you want to create your own abstract classes set:
        __abstract_node__ = True
    """

    # static properties

    __abstract_node__ = True

    # magic methods

    def __init__(self, *args: Any, **kwargs: Any):
        if "deleted" in kwargs:
            raise ValueError("deleted property is reserved for neomodel")

        for key, val in self.__all_relationships__:
            self.__dict__[key] = val.build_manager(self, key)

        super().__init__(*args, **kwargs)

    def __eq__(self, other: Any) -> bool:
        """
        Compare two node objects.
        If both nodes were saved to the database, compare them by their element_id.
        Otherwise, compare them using object id in memory.
        If `other` is not a node, always return False.
        """
        if not isinstance(other, (StructuredNode,)):
            return False
        if self.was_saved and other.was_saved:
            return self.element_id == other.element_id
        return id(self) == id(other)

    def __ne__(self, other: Any) -> bool:
        return not self.__eq__(other)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self}>"

    def __str__(self) -> str:
        return repr(self.__properties__)

    # dynamic properties

    @classproperty
    def nodes(self) -> Any:
        """
        Returns a NodeSet object representing all nodes of the classes label
        :return: NodeSet
        :rtype: NodeSet
        """
        from neomodel.sync_.match import NodeSet

        return NodeSet(self)

    @property
    def element_id(self) -> Optional[Any]:
        if hasattr(self, "element_id_property"):
            return self.element_id_property
        return None

    # Version 4.4 support - id is deprecated in version 5.x
    @property
    def id(self) -> int:
        try:
            return int(self.element_id_property)
        except (TypeError, ValueError):
            raise ValueError(
                "id is deprecated in Neo4j version 5, please migrate to element_id. If you use the id in a Cypher query, replace id() by elementId()."
            )

    @property
    def was_saved(self) -> bool:
        """
        Shows status of node in the database. False, if node hasn't been saved yet, True otherwise.
        """
        return self.element_id is not None

    # methods

    @classmethod
    def _build_merge_query(
        cls,
        merge_params: tuple[dict[str, Any], ...],
        update_existing: bool = False,
        lazy: bool = False,
        relationship: Optional[Any] = None,
    ) -> tuple[str, dict[str, Any]]:
        """
        Get a tuple of a CYPHER query and a params dict for the specified MERGE query.

        :param merge_params: The target node match parameters, each node must have a "create" key and optional "update".
        :type merge_params: list of dict
        :param update_existing: True to update properties of existing nodes, default False to keep existing values.
        :type update_existing: bool
        :rtype: tuple
        """
        query_params: dict[str, Any] = {"merge_params": merge_params}
        n_merge_labels = ":".join(cls.inherited_labels())
        n_merge_prm = ", ".join(
            (
                f"{getattr(cls, p).get_db_property_name(p)}: params.create.{getattr(cls, p).get_db_property_name(p)}"
                for p in cls.__required_properties__
            )
        )
        n_merge = f"n:{n_merge_labels} {{{n_merge_prm}}}"
        if relationship is None:
            # create "simple" unwind query
            query = f"UNWIND $merge_params as params\n MERGE ({n_merge})\n "
        else:
            # validate relationship
            if not isinstance(relationship.source, StructuredNode):
                raise ValueError(
                    f"relationship source [{repr(relationship.source)}] is not a StructuredNode"
                )
            relation_type = relationship.definition.get("relation_type")
            if not relation_type:
                raise ValueError(
                    "No relation_type is specified on provided relationship"
                )

            from neomodel.sync_.match import _rel_helper

            if relationship.source.element_id is None:
                raise RuntimeError(
                    "Could not identify the relationship source, its element id was None."
                )
            query_params["source_id"] = db.parse_element_id(
                relationship.source.element_id
            )
            query = f"MATCH (source:{relationship.source.__label__}) WHERE {db.get_id_method()}(source) = $source_id\n "
            query += "WITH source\n UNWIND $merge_params as params \n "
            query += "MERGE "
            query += _rel_helper(
                lhs="source",
                rhs=n_merge,
                ident=None,
                relation_type=relation_type,
                direction=relationship.definition["direction"],
            )

        query += "ON CREATE SET n = params.create\n "
        # if update_existing, write properties on match as well
        if update_existing is True:
            query += "ON MATCH SET n += params.update\n"

        # close query
        if lazy:
            query += f"RETURN {db.get_id_method()}(n)"
        else:
            query += "RETURN n"

        return query, query_params

    @classmethod
    def create(cls, *props: tuple, **kwargs: dict[str, Any]) -> list:
        """
        Call to CREATE with parameters map. A new instance will be created and saved.

        :param props: dict of properties to create the nodes.
        :type props: tuple
        :param lazy: False by default, specify True to get nodes with id only without the parameters.
        :type: bool
        :rtype: list
        """

        if "streaming" in kwargs:
            warnings.warn(
                STREAMING_WARNING,
                category=DeprecationWarning,
                stacklevel=1,
            )

        lazy = kwargs.get("lazy", False)
        # create mapped query
        query = f"CREATE (n:{':'.join(cls.inherited_labels())} $create_params)"

        # close query
        if lazy:
            query += f" RETURN {db.get_id_method()}(n)"
        else:
            query += " RETURN n"

        results = []
        for item in [
            cls.deflate(p, obj=_UnsavedNode(), skip_empty=True) for p in props
        ]:
            node, _ = db.cypher_query(query, {"create_params": item})
            results.extend(node[0])

        nodes = [cls.inflate(node) for node in results]

        if not lazy and hasattr(cls, "post_create"):
            for node in nodes:
                node.post_create()

        return nodes

    @classmethod
    def create_or_update(cls, *props: tuple, **kwargs: dict[str, Any]) -> list:
        """
        Call to MERGE with parameters map. A new instance will be created and saved if does not already exists,
        this is an atomic operation. If an instance already exists all optional properties specified will be updated.

        Note that the post_create hook isn't called after create_or_update

        :param props: List of dict arguments to get or create the entities with.
        :type props: tuple
        :param relationship: Optional, relationship to get/create on when new entity is created.
        :param lazy: False by default, specify True to get nodes with id only without the parameters.
        :rtype: list
        """
        lazy: bool = bool(kwargs.get("lazy", False))
        relationship = kwargs.get("relationship")

        # build merge query, make sure to update only explicitly specified properties
        create_or_update_params = []
        for specified, deflated in [
            (p, cls.deflate(p, skip_empty=True)) for p in props
        ]:
            create_or_update_params.append(
                {
                    "create": deflated,
                    "update": dict(
                        (k, v) for k, v in deflated.items() if k in specified
                    ),
                }
            )
        query, params = cls._build_merge_query(
            tuple(create_or_update_params),
            update_existing=True,
            relationship=relationship,
            lazy=lazy,
        )

        if "streaming" in kwargs:
            warnings.warn(
                STREAMING_WARNING,
                category=DeprecationWarning,
                stacklevel=1,
            )

        # fetch and build instance for each result
        results = db.cypher_query(query, params)
        return [cls.inflate(r[0]) for r in results[0]]

    def cypher(
        self, query: str, params: Optional[dict[str, Any]] = None
    ) -> tuple[Optional[list], Optional[tuple[str, ...]]]:
        """
        Execute a cypher query with the param 'self' pre-populated with the nodes neo4j id.

        :param query: cypher query string
        :type: string
        :param params: query parameters
        :type: dict
        :return: tuple containing a list of query results, and the meta information as a tuple
        :rtype: tuple
        """
        self._pre_action_check("cypher")
        _params = params or {}
        if self.element_id is None:
            raise ValueError("Can't run cypher operation on unsaved node")
        element_id = db.parse_element_id(self.element_id)
        _params.update({"self": element_id})
        return db.cypher_query(query, _params)

    @hooks
    def delete(self) -> bool:
        """
        Delete a node and its relationships

        :return: True
        """
        self._pre_action_check("delete")
        self.cypher(
            f"MATCH (self) WHERE {db.get_id_method()}(self)=$self DETACH DELETE self"
        )
        delattr(self, "element_id_property")
        self.deleted = True
        return True

    @classmethod
    def get_or_create(cls: Any, *props: tuple, **kwargs: dict[str, Any]) -> list:
        """
        Call to MERGE with parameters map. A new instance will be created and saved if does not already exist,
        this is an atomic operation.
        Parameters must contain all required properties, any non required properties with defaults will be generated.

        Note that the post_create hook isn't called after get_or_create

        :param props: Arguments to get_or_create as tuple of dict with property names and values to get or create
                      the entities with.
        :type props: tuple
        :param relationship: Optional, relationship to get/create on when new entity is created.
        :param lazy: False by default, specify True to get nodes with id only without the parameters.
        :rtype: list
        """
        lazy = kwargs.get("lazy", False)
        relationship = kwargs.get("relationship")

        # build merge query
        get_or_create_params = [
            {"create": cls.deflate(p, skip_empty=True)} for p in props
        ]
        query, params = cls._build_merge_query(
            tuple(get_or_create_params), relationship=relationship, lazy=lazy
        )

        if "streaming" in kwargs:
            warnings.warn(
                STREAMING_WARNING,
                category=DeprecationWarning,
                stacklevel=1,
            )

        # fetch and build instance for each result
        results = db.cypher_query(query, params)
        return [cls.inflate(r[0]) for r in results[0]]

    @classmethod
    def inflate(cls: Any, node: Any) -> Any:
        """
        Inflate a raw neo4j_driver node to a neomodel node
        :param node:
        :return: node object
        """
        # support lazy loading
        if isinstance(node, str) or isinstance(node, int):
            snode = cls()
            snode.element_id_property = node
        else:
            snode = super().inflate(node)
            snode.element_id_property = node.element_id

        return snode

    @classmethod
    def inherited_labels(cls: Any) -> list[str]:
        """
        Return list of labels from nodes class hierarchy.

        :return: list
        """
        return [
            scls.__label__
            for scls in cls.mro()
            if hasattr(scls, "__label__") and not hasattr(scls, "__abstract_node__")
        ]

    @classmethod
    def inherited_optional_labels(cls: Any) -> list[str]:
        """
        Return list of optional labels from nodes class hierarchy.

        :return: list
        :rtype: list
        """
        return [
            label
            for scls in cls.mro()
            for label in getattr(scls, "__optional_labels__", [])
            if not hasattr(scls, "__abstract_node__")
        ]

    def labels(self) -> list[str]:
        """
        Returns list of labels tied to the node from neo4j.

        :return: list of labels
        :rtype: list
        """
        self._pre_action_check("labels")
        result = self.cypher(
            f"MATCH (n) WHERE {db.get_id_method()}(n)=$self " "RETURN labels(n)"
        )
        if result is None or result[0] is None:
            raise ValueError("Could not get labels, node may not exist")
        return result[0][0][0]

    def _pre_action_check(self, action: str) -> None:
        if hasattr(self, "deleted") and self.deleted:
            raise ValueError(
                f"{self.__class__.__name__}.{action}() attempted on deleted node"
            )
        if not hasattr(self, "element_id"):
            raise ValueError(
                f"{self.__class__.__name__}.{action}() attempted on unsaved node"
            )

    def refresh(self) -> None:
        """
        Reload the node from neo4j
        """
        self._pre_action_check("refresh")
        if hasattr(self, "element_id"):
            results = self.cypher(
                f"MATCH (n) WHERE {db.get_id_method()}(n)=$self RETURN n"
            )
            request = results[0]
            if not request or not request[0]:
                raise self.__class__.DoesNotExist("Can't refresh non existent node")
            node = self.inflate(request[0][0])
            for key, val in node.__properties__.items():
                setattr(self, key, val)
        else:
            raise ValueError("Can't refresh unsaved node")

    @hooks
    def save(self) -> "StructuredNode":
        """
        Save the node to neo4j or raise an exception

        :return: the node instance
        """

        # create or update instance node
        if hasattr(self, "element_id_property"):
            # update
            params = self.deflate(self.__properties__, self)
            query = f"MATCH (n) WHERE {db.get_id_method()}(n)=$self\n"

            if params:
                query += "SET "
                query += ",\n".join([f"n.{key} = ${key}" for key in params])
                query += "\n"
            if self.inherited_labels():
                query += "\n".join(
                    [f"SET n:`{label}`" for label in self.inherited_labels()]
                )
            self.cypher(query, params)
        elif hasattr(self, "deleted") and self.deleted:
            raise ValueError(
                f"{self.__class__.__name__}.save() attempted on deleted node"
            )
        else:  # create
            result = self.create(self.__properties__)
            created_node = result[0]
            self.element_id_property = created_node.element_id
        return self
