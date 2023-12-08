import logging
import os
import sys
import time
import warnings
from threading import local
from typing import Optional, Sequence
from urllib.parse import quote, unquote, urlparse

from neo4j import DEFAULT_DATABASE, Driver, GraphDatabase, basic_auth
from neo4j.api import Bookmarks
from neo4j.exceptions import ClientError, ServiceUnavailable, SessionExpired
from neo4j.graph import Node, Path, Relationship

from neomodel import config, core
from neomodel.exceptions import (
    ConstraintValidationFailed,
    FeatureNotSupported,
    NodeClassNotDefined,
    RelationshipClassNotDefined,
    UniqueProperty,
)

logger = logging.getLogger(__name__)


# make sure the connection url has been set prior to executing the wrapped function
def ensure_connection(func):
    def wrapper(self, *args, **kwargs):
        # Sort out where to find url
        if hasattr(self, "db"):
            _db = self.db
        else:
            _db = self

        if not _db.driver:
            if hasattr(config, "DRIVER") and config.DRIVER:
                _db.set_connection(driver=config.DRIVER)
            elif config.DATABASE_URL:
                _db.set_connection(url=config.DATABASE_URL)

        return func(self, *args, **kwargs)

    return wrapper


def change_neo4j_password(db, user, new_password):
    db.cypher_query(f"ALTER USER {user} SET PASSWORD '{new_password}'")


def clear_neo4j_database(db, clear_constraints=False, clear_indexes=False):
    db.cypher_query(
        """
        MATCH (a)
        CALL { WITH a DETACH DELETE a }
        IN TRANSACTIONS OF 5000 rows
    """
    )
    if clear_constraints:
        core.drop_constraints()
    if clear_indexes:
        core.drop_indexes()


class Database(local):
    """
    A singleton object via which all operations from neomodel to the Neo4j backend are handled with.
    """

    _NODE_CLASS_REGISTRY = {}

    def __init__(self):
        self._active_transaction = None
        self.url = None
        self.driver = None
        self._session = None
        self._pid = None
        self._database_name = DEFAULT_DATABASE
        self.protocol_version = None
        self._database_version = None
        self._database_edition = None
        self.impersonated_user = None

    def set_connection(self, url: str = None, driver: Driver = None):
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

        self.driver = GraphDatabase.driver(
            parsed_url.scheme + "://" + hostname, **options
        )
        self.url = url
        # The database name can be provided through the url or the config
        if database_name == "":
            if hasattr(config, "DATABASE_NAME") and config.DATABASE_NAME:
                self._database_name = config.DATABASE_NAME
        else:
            self._database_name = database_name

    def close_connection(self):
        """
        Closes the currently open driver.
        The driver should always be closed at the end of the application's lifecyle.
        """
        self._database_version = None
        self._database_edition = None
        self._database_name = None
        self.driver.close()
        self.driver = None

    @property
    def database_version(self):
        if self._database_version is None:
            self._update_database_version()

        return self._database_version

    @property
    def database_edition(self):
        if self._database_edition is None:
            self._update_database_version()

        return self._database_edition

    @property
    def transaction(self):
        """
        Returns the current transaction object
        """
        return TransactionProxy(self)

    @property
    def write_transaction(self):
        return TransactionProxy(self, access_mode="WRITE")

    @property
    def read_transaction(self):
        return TransactionProxy(self, access_mode="READ")

    def impersonate(self, user: str) -> "ImpersonationHandler":
        """All queries executed within this context manager will be executed as impersonated user

        Args:
            user (str): User to impersonate

        Returns:
            ImpersonationHandler: Context manager to set/unset the user to impersonate
        """
        if self.database_edition != "enterprise":
            raise FeatureNotSupported(
                "Impersonation is only available in Neo4j Enterprise edition"
            )
        return ImpersonationHandler(self, impersonated_user=user)

    @ensure_connection
    def begin(self, access_mode=None, **parameters):
        """
        Begins a new transaction. Raises SystemError if a transaction is already active.
        """
        if (
            hasattr(self, "_active_transaction")
            and self._active_transaction is not None
        ):
            raise SystemError("Transaction in progress")
        self._session = self.driver.session(
            default_access_mode=access_mode,
            database=self._database_name,
            impersonated_user=self.impersonated_user,
            **parameters,
        )
        self._active_transaction = self._session.begin_transaction()

    @ensure_connection
    def commit(self):
        """
        Commits the current transaction and closes its session

        :return: last_bookmarks
        """
        try:
            self._active_transaction.commit()
            last_bookmarks = self._session.last_bookmarks()
        finally:
            # In case when something went wrong during
            # committing changes to the database
            # we have to close an active transaction and session.
            self._active_transaction.close()
            self._session.close()
            self._active_transaction = None
            self._session = None

        return last_bookmarks

    @ensure_connection
    def rollback(self):
        """
        Rolls back the current transaction and closes its session
        """
        try:
            self._active_transaction.rollback()
        finally:
            # In case when something went wrong during changes rollback,
            # we have to close an active transaction and session
            self._active_transaction.close()
            self._session.close()
            self._active_transaction = None
            self._session = None

    def _update_database_version(self):
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

    def _object_resolution(self, object_to_resolve):
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
            return self._NODE_CLASS_REGISTRY[
                frozenset(object_to_resolve.labels)
            ].inflate(object_to_resolve)

        if isinstance(object_to_resolve, Relationship):
            rel_type = frozenset([object_to_resolve.type])
            return self._NODE_CLASS_REGISTRY[rel_type].inflate(object_to_resolve)

        if isinstance(object_to_resolve, Path):
            from .path import NeomodelPath

            return NeomodelPath(object_to_resolve)

        if isinstance(object_to_resolve, list):
            return self._result_resolution([object_to_resolve])

        return object_to_resolve

    def _result_resolution(self, result_list):
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
                try:
                    # Primitive types should remain primitive types,
                    # Nodes to be resolved to native objects
                    resolved_object = a_result_attribute[1]

                    resolved_object = self._object_resolution(resolved_object)

                    result_list[a_result_item[0]][
                        a_result_attribute[0]
                    ] = resolved_object

                except KeyError as exc:
                    # Not being able to match the label set of a node with a known object results
                    # in a KeyError in the internal dictionary used for resolution. If it is impossible
                    # to match, then raise an exception with more details about the error.
                    if isinstance(a_result_attribute[1], Node):
                        raise NodeClassNotDefined(
                            a_result_attribute[1], self._NODE_CLASS_REGISTRY
                        ) from exc

                    if isinstance(a_result_attribute[1], Relationship):
                        raise RelationshipClassNotDefined(
                            a_result_attribute[1], self._NODE_CLASS_REGISTRY
                        ) from exc

        return result_list

    @ensure_connection
    def cypher_query(
        self,
        query,
        params=None,
        handle_unique=True,
        retry_on_session_expire=False,
        resolve_objects=False,
    ):
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
        """

        if self._active_transaction:
            # Use current session is a transaction is currently active
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
            with self.driver.session(
                database=self._database_name, impersonated_user=self.impersonated_user
            ) as session:
                results, meta = self._run_cypher_query(
                    session,
                    query,
                    params,
                    handle_unique,
                    retry_on_session_expire,
                    resolve_objects,
                )

        return results, meta

    def _run_cypher_query(
        self,
        session,
        query,
        params,
        handle_unique,
        retry_on_session_expire,
        resolve_objects,
    ):
        try:
            # Retrieve the data
            start = time.time()
            response = session.run(query, params)
            results, meta = [list(r.values()) for r in response], response.keys()
            end = time.time()

            if resolve_objects:
                # Do any automatic resolution required
                results = self._result_resolution(results)

        except ClientError as e:
            if e.code == "Neo.ClientError.Schema.ConstraintValidationFailed":
                if "already exists with label" in e.message and handle_unique:
                    raise UniqueProperty(e.message) from e

                raise ConstraintValidationFailed(e.message) from e
            exc_info = sys.exc_info()
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
        if self.database_version.startswith("4"):
            return "id"
        else:
            return "elementId"

    def list_indexes(self, exclude_token_lookup=False) -> Sequence[dict]:
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

    def list_constraints(self) -> Sequence[dict]:
        """Returns all constraints existing in the database

        Returns:
            Sequence[dict]: List of dictionaries, each entry being a constraint definition
        """
        constraints, meta_constraints = self.cypher_query("SHOW CONSTRAINTS")
        constraints_as_dict = [dict(zip(meta_constraints, row)) for row in constraints]

        return constraints_as_dict

    def version_is_higher_than(self, version_tag: str) -> bool:
        """Returns true if the database version is higher or equal to a given tag

        Args:
            version_tag (str): The version to compare against

        Returns:
            bool: True if the database version is higher or equal to the given version
        """
        return version_tag_to_integer(self.database_version) >= version_tag_to_integer(
            version_tag
        )

    def edition_is_enterprise(self) -> bool:
        """Returns true if the database edition is enterprise

        Returns:
            bool: True if the database edition is enterprise
        """
        return self.database_edition == "enterprise"


class TransactionProxy:
    bookmarks: Optional[Bookmarks] = None

    def __init__(self, db, access_mode=None):
        self.db = db
        self.access_mode = access_mode

    @ensure_connection
    def __enter__(self):
        self.db.begin(access_mode=self.access_mode, bookmarks=self.bookmarks)
        self.bookmarks = None
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_value:
            self.db.rollback()

        if (
            exc_type is ClientError
            and exc_value.code == "Neo.ClientError.Schema.ConstraintValidationFailed"
        ):
            raise UniqueProperty(exc_value.message)

        if not exc_value:
            self.last_bookmark = self.db.commit()

    def __call__(self, func):
        def wrapper(*args, **kwargs):
            with self:
                return func(*args, **kwargs)

        return wrapper

    @property
    def with_bookmark(self):
        return BookmarkingTransactionProxy(self.db, self.access_mode)


class ImpersonationHandler:
    def __init__(self, db, impersonated_user: str):
        self.db = db
        self.impersonated_user = impersonated_user

    def __enter__(self):
        self.db.impersonated_user = self.impersonated_user
        return self

    def __exit__(self, exception_type, exception_value, exception_traceback):
        self.db.impersonated_user = None

        print("\nException type:", exception_type)
        print("\nException value:", exception_value)
        print("\nTraceback:", exception_traceback)

    def __call__(self, func):
        def wrapper(*args, **kwargs):
            with self:
                return func(*args, **kwargs)

        return wrapper


class BookmarkingTransactionProxy(TransactionProxy):
    def __call__(self, func):
        def wrapper(*args, **kwargs):
            self.bookmarks = kwargs.pop("bookmarks", None)

            with self:
                result = func(*args, **kwargs)
                self.last_bookmark = None

            return result, self.last_bookmark

        return wrapper


def deprecated(message):
    # pylint:disable=invalid-name
    def f__(f):
        def f_(*args, **kwargs):
            warnings.warn(message, category=DeprecationWarning, stacklevel=2)
            return f(*args, **kwargs)

        f_.__name__ = f.__name__
        f_.__doc__ = f.__doc__
        f_.__dict__.update(f.__dict__)
        return f_

    return f__


def classproperty(f):
    class cpf:
        def __init__(self, getter):
            self.getter = getter

        def __get__(self, obj, type=None):
            return self.getter(type)

    return cpf(f)


# Just used for error messages
class _UnsavedNode:
    def __repr__(self):
        return "<unsaved node>"

    def __str__(self):
        return self.__repr__()


def _get_node_properties(node):
    """Get the properties from a neo4j.vx.types.graph.Node object."""
    return node._properties


def enumerate_traceback(initial_frame):
    depth, frame = 0, initial_frame
    while frame is not None:
        yield depth, frame
        frame = frame.f_back
        depth += 1


def version_tag_to_integer(version_tag):
    """
    Converts a version string to an integer representation to allow for quick comparisons between versions.

    :param a_version_string: The version string to be converted (e.g. '5.4.0')
    :type a_version_string: str
    :return: An integer representation of the version string (e.g. '5.4.0' --> 50400)
    :rtype: int
    """
    components = version_tag.split(".")
    while len(components) < 3:
        components.append("0")
    num = 0
    for index, component in enumerate(components):
        # Aura started adding a -aura suffix in version numbers, like "5.14-aura"
        # This will strip the suffix to allow for proper comparison : 14 instead of 14-aura
        if "-" in component:
            component = component.split("-")[0]
        num += (100 ** ((len(components) - 1) - index)) * int(component)
    return num
