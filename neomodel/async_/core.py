from __future__ import annotations

import logging
import os
import sys
import time
import warnings
from asyncio import iscoroutinefunction
from functools import wraps
from itertools import combinations
from threading import local
from typing import Any, Optional, Sequence
from urllib.parse import quote, unquote, urlparse

from neo4j import (
    DEFAULT_DATABASE,
    AsyncDriver,
    AsyncGraphDatabase,
    AsyncResult,
    AsyncSession,
    AsyncTransaction,
    basic_auth,
)
from neo4j.api import Bookmarks
from neo4j.exceptions import ClientError, ServiceUnavailable, SessionExpired
from neo4j.graph import Node, Path, Relationship

from neomodel import config
from neomodel._async_compat.util import AsyncUtil
from neomodel.async_.property_manager import AsyncPropertyManager
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
def ensure_connection(func):
    """Decorator that ensures a connection is established before executing the decorated function.

    Args:
        func (callable): The function to be decorated.

    Returns:
        callable: The decorated function.

    """

    async def wrapper(self, *args, **kwargs):
        # Sort out where to find url
        if hasattr(self, "db"):
            _db = self.db
        else:
            _db = self

        if not _db.driver:
            if hasattr(config, "DATABASE_URL") and config.DATABASE_URL:
                await _db.set_connection(url=config.DATABASE_URL)
            elif hasattr(config, "DRIVER") and config.DRIVER:
                await _db.set_connection(driver=config.DRIVER)

        return await func(self, *args, **kwargs)

    return wrapper


class AsyncDatabase(local):
    """
    A singleton object via which all operations from neomodel to the Neo4j backend are handled with.
    """

    _NODE_CLASS_REGISTRY = {}
    _DB_SPECIFIC_CLASS_REGISTRY = {}

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

    async def set_connection(self, url: str = None, driver: AsyncDriver = None):
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
        await self._update_database_version()

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

        self.driver = AsyncGraphDatabase.driver(
            parsed_url.scheme + "://" + hostname, **options
        )
        self.url = url
        # The database name can be provided through the url or the config
        if database_name == "":
            if hasattr(config, "DATABASE_NAME") and config.DATABASE_NAME:
                self._database_name = config.DATABASE_NAME
        else:
            self._database_name = database_name

    async def close_connection(self):
        """
        Closes the currently open driver.
        The driver should always be closed at the end of the application's lifecyle.
        """
        self._database_version = None
        self._database_edition = None
        self._database_name = None
        await self.driver.close()
        self.driver = None

    @property
    async def database_version(self):
        if self._database_version is None:
            await self._update_database_version()

        return self._database_version

    @property
    async def database_edition(self):
        if self._database_edition is None:
            await self._update_database_version()

        return self._database_edition

    @property
    def transaction(self):
        """
        Returns the current transaction object
        """
        return AsyncTransactionProxy(self)

    @property
    def write_transaction(self):
        return AsyncTransactionProxy(self, access_mode="WRITE")

    @property
    def read_transaction(self):
        return AsyncTransactionProxy(self, access_mode="READ")

    async def impersonate(self, user: str) -> "ImpersonationHandler":
        """All queries executed within this context manager will be executed as impersonated user

        Args:
            user (str): User to impersonate

        Returns:
            ImpersonationHandler: Context manager to set/unset the user to impersonate
        """
        db_edition = await self.database_edition
        if db_edition != "enterprise":
            raise FeatureNotSupported(
                "Impersonation is only available in Neo4j Enterprise edition"
            )
        return ImpersonationHandler(self, impersonated_user=user)

    @ensure_connection
    async def begin(self, access_mode=None, **parameters):
        """
        Begins a new transaction. Raises SystemError if a transaction is already active.
        """
        if (
            hasattr(self, "_active_transaction")
            and self._active_transaction is not None
        ):
            raise SystemError("Transaction in progress")
        self._session: AsyncSession = self.driver.session(
            default_access_mode=access_mode,
            database=self._database_name,
            impersonated_user=self.impersonated_user,
            **parameters,
        )
        self._active_transaction: AsyncTransaction = (
            await self._session.begin_transaction()
        )

    @ensure_connection
    async def commit(self):
        """
        Commits the current transaction and closes its session

        :return: last_bookmarks
        """
        try:
            await self._active_transaction.commit()
            last_bookmarks: Bookmarks = await self._session.last_bookmarks()
        finally:
            # In case when something went wrong during
            # committing changes to the database
            # we have to close an active transaction and session.
            await self._active_transaction.close()
            await self._session.close()
            self._active_transaction = None
            self._session = None

        return last_bookmarks

    @ensure_connection
    async def rollback(self):
        """
        Rolls back the current transaction and closes its session
        """
        try:
            await self._active_transaction.rollback()
        finally:
            # In case when something went wrong during changes rollback,
            # we have to close an active transaction and session
            await self._active_transaction.close()
            await self._session.close()
            self._active_transaction = None
            self._session = None

    async def _update_database_version(self):
        """
        Updates the database server information when it is required
        """
        try:
            results = await self.cypher_query(
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
            from neomodel.async_.path import AsyncNeomodelPath

            return AsyncNeomodelPath(object_to_resolve)

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
                # Primitive types should remain primitive types,
                # Nodes to be resolved to native objects
                resolved_object = a_result_attribute[1]

                resolved_object = self._object_resolution(resolved_object)

                result_list[a_result_item[0]][a_result_attribute[0]] = resolved_object

        return result_list

    @ensure_connection
    async def cypher_query(
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

        :return: A tuple containing a list of results and a tuple of headers.
        """

        if self._active_transaction:
            # Use current session is a transaction is currently active
            results, meta = await self._run_cypher_query(
                self._active_transaction,
                query,
                params,
                handle_unique,
                retry_on_session_expire,
                resolve_objects,
            )
        else:
            # Otherwise create a new session in a with to dispose of it after it has been run
            async with self.driver.session(
                database=self._database_name, impersonated_user=self.impersonated_user
            ) as session:
                results, meta = await self._run_cypher_query(
                    session,
                    query,
                    params,
                    handle_unique,
                    retry_on_session_expire,
                    resolve_objects,
                )

        return results, meta

    async def _run_cypher_query(
        self,
        session: AsyncSession,
        query,
        params,
        handle_unique,
        retry_on_session_expire,
        resolve_objects,
    ):
        try:
            # Retrieve the data
            start = time.time()
            response: AsyncResult = await session.run(query, params)
            results, meta = [list(r.values()) async for r in response], response.keys()
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
                await self.set_connection(url=self.url)
                return await self.cypher_query(
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

    async def get_id_method(self) -> str:
        db_version = await self.database_version
        if db_version.startswith("4"):
            return "id"
        else:
            return "elementId"

    async def parse_element_id(self, element_id: str):
        db_version = await self.database_version
        return int(element_id) if db_version.startswith("4") else element_id

    async def list_indexes(self, exclude_token_lookup=False) -> Sequence[dict]:
        """Returns all indexes existing in the database

        Arguments:
            exclude_token_lookup[bool]: Exclude automatically create token lookup indexes

        Returns:
            Sequence[dict]: List of dictionaries, each entry being an index definition
        """
        indexes, meta_indexes = await self.cypher_query("SHOW INDEXES")
        indexes_as_dict = [dict(zip(meta_indexes, row)) for row in indexes]

        if exclude_token_lookup:
            indexes_as_dict = [
                obj for obj in indexes_as_dict if obj["type"] != "LOOKUP"
            ]

        return indexes_as_dict

    async def list_constraints(self) -> Sequence[dict]:
        """Returns all constraints existing in the database

        Returns:
            Sequence[dict]: List of dictionaries, each entry being a constraint definition
        """
        constraints, meta_constraints = await self.cypher_query("SHOW CONSTRAINTS")
        constraints_as_dict = [dict(zip(meta_constraints, row)) for row in constraints]

        return constraints_as_dict

    @ensure_connection
    async def version_is_higher_than(self, version_tag: str) -> bool:
        """Returns true if the database version is higher or equal to a given tag

        Args:
            version_tag (str): The version to compare against

        Returns:
            bool: True if the database version is higher or equal to the given version
        """
        db_version = await self.database_version
        return version_tag_to_integer(db_version) >= version_tag_to_integer(version_tag)

    @ensure_connection
    async def edition_is_enterprise(self) -> bool:
        """Returns true if the database edition is enterprise

        Returns:
            bool: True if the database edition is enterprise
        """
        edition = await self.database_edition
        return edition == "enterprise"

    async def change_neo4j_password(self, user, new_password):
        await self.cypher_query(f"ALTER USER {user} SET PASSWORD '{new_password}'")

    async def clear_neo4j_database(self, clear_constraints=False, clear_indexes=False):
        await self.cypher_query(
            """
            MATCH (a)
            CALL { WITH a DETACH DELETE a }
            IN TRANSACTIONS OF 5000 rows
        """
        )
        if clear_constraints:
            await drop_constraints()
        if clear_indexes:
            await drop_indexes()

    async def drop_constraints(self, quiet=True, stdout=None):
        """
        Discover and drop all constraints.

        :type: bool
        :return: None
        """
        if not stdout or stdout is None:
            stdout = sys.stdout

        results, meta = await self.cypher_query("SHOW CONSTRAINTS")

        results_as_dict = [dict(zip(meta, row)) for row in results]
        for constraint in results_as_dict:
            await self.cypher_query("DROP CONSTRAINT " + constraint["name"])
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

    async def drop_indexes(self, quiet=True, stdout=None):
        """
        Discover and drop all indexes, except the automatically created token lookup indexes.

        :type: bool
        :return: None
        """
        if not stdout or stdout is None:
            stdout = sys.stdout

        indexes = await self.list_indexes(exclude_token_lookup=True)
        for index in indexes:
            await self.cypher_query("DROP INDEX " + index["name"])
            if not quiet:
                stdout.write(
                    f' - Dropping index on labels {",".join(index["labelsOrTypes"])} with properties {",".join(index["properties"])}.\n'
                )
        if not quiet:
            stdout.write("\n")

    async def remove_all_labels(self, stdout=None):
        """
        Calls functions for dropping constraints and indexes.

        :param stdout: output stream
        :return: None
        """

        if not stdout:
            stdout = sys.stdout

        stdout.write("Dropping constraints...\n")
        await self.drop_constraints(quiet=False, stdout=stdout)

        stdout.write("Dropping indexes...\n")
        await self.drop_indexes(quiet=False, stdout=stdout)

    async def install_all_labels(self, stdout=None):
        """
        Discover all subclasses of StructuredNode in your application and execute install_labels on each.
        Note: code must be loaded (imported) in order for a class to be discovered.

        :param stdout: output stream
        :return: None
        """

        if not stdout or stdout is None:
            stdout = sys.stdout

        def subsub(cls):  # recursively return all subclasses
            subclasses = cls.__subclasses__()
            if not subclasses:  # base case: no more subclasses
                return []
            return subclasses + [g for s in cls.__subclasses__() for g in subsub(s)]

        stdout.write("Setting up indexes and constraints...\n\n")

        i = 0
        for cls in subsub(AsyncStructuredNode):
            stdout.write(f"Found {cls.__module__}.{cls.__name__}\n")
            await install_labels(cls, quiet=False, stdout=stdout)
            i += 1

        if i:
            stdout.write("\n")

        stdout.write(f"Finished {i} classes.\n")

    async def install_labels(self, cls, quiet=True, stdout=None):
        """
        Setup labels with indexes and constraints for a given class

        :param cls: StructuredNode class
        :type: class
        :param quiet: (default true) enable standard output
        :param stdout: stdout stream
        :type: bool
        :return: None
        """
        if not stdout or stdout is None:
            stdout = sys.stdout

        if not hasattr(cls, "__label__"):
            if not quiet:
                stdout.write(
                    f" ! Skipping class {cls.__module__}.{cls.__name__} is abstract\n"
                )
            return

        for name, property in cls.defined_properties(aliases=False, rels=False).items():
            await self._install_node(cls, name, property, quiet, stdout)

        for _, relationship in cls.defined_properties(
            aliases=False, rels=True, properties=False
        ).items():
            await self._install_relationship(cls, relationship, quiet, stdout)

    async def _create_node_index(
        self, target_cls, property_name: str, stdout, quiet: bool
    ):
        label = target_cls.__label__
        index_name = f"index_{label}_{property_name}"
        if not quiet:
            stdout.write(
                f" + Creating node index for {property_name} on label {label} for class {target_cls.__module__}.{target_cls.__name__}\n"
            )
        try:
            await self.cypher_query(
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

    async def _create_node_fulltext_index(
        self,
        target_cls,
        property_name: str,
        stdout,
        fulltext_index: FulltextIndex,
        quiet: bool,
    ):
        if await self.version_is_higher_than("5.16"):
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
                await self.cypher_query(query)
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
                f"Creation of full-text indexes from neomodel is not supported for Neo4j in version {await self.database_version}. Please upgrade to Neo4j 5.16 or higher."
            )

    async def _create_node_vector_index(
        self,
        target_cls,
        property_name: str,
        stdout,
        vector_index: VectorIndex,
        quiet: bool,
    ):
        if await self.version_is_higher_than("5.15"):
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
                await self.cypher_query(query)
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
                f"Creation of vector indexes from neomodel is not supported for Neo4j in version {await self.database_version}. Please upgrade to Neo4j 5.15 or higher."
            )

    async def _create_node_constraint(
        self, target_cls, property_name: str, stdout, quiet: bool
    ):
        label = target_cls.__label__
        constraint_name = f"constraint_unique_{label}_{property_name}"
        if not quiet:
            stdout.write(
                f" + Creating node unique constraint for {property_name} on label {target_cls.__label__} for class {target_cls.__module__}.{target_cls.__name__}\n"
            )
        try:
            await self.cypher_query(
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

    async def _create_relationship_index(
        self,
        relationship_type: str,
        target_cls,
        relationship_cls,
        property_name: str,
        stdout,
        quiet: bool,
    ):
        index_name = f"index_{relationship_type}_{property_name}"
        if not quiet:
            stdout.write(
                f" + Creating relationship index for {property_name} on relationship type {relationship_type} for relationship model {target_cls.__module__}.{relationship_cls.__name__}\n"
            )
        try:
            await self.cypher_query(
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

    async def _create_relationship_fulltext_index(
        self,
        relationship_type: str,
        target_cls,
        relationship_cls,
        property_name: str,
        stdout,
        fulltext_index: FulltextIndex,
        quiet: bool,
    ):
        if await self.version_is_higher_than("5.16"):
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
                await self.cypher_query(query)
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
                f"Creation of full-text indexes from neomodel is not supported for Neo4j in version {await self.database_version}. Please upgrade to Neo4j 5.16 or higher."
            )

    async def _create_relationship_vector_index(
        self,
        relationship_type: str,
        target_cls,
        relationship_cls,
        property_name: str,
        stdout,
        vector_index: VectorIndex,
        quiet: bool,
    ):
        if await self.version_is_higher_than("5.18"):
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
                await self.cypher_query(query)
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
                f"Creation of vector indexes for relationships from neomodel is not supported for Neo4j in version {await self.database_version}. Please upgrade to Neo4j 5.18 or higher."
            )

    async def _create_relationship_constraint(
        self,
        relationship_type: str,
        target_cls,
        relationship_cls,
        property_name: str,
        stdout,
        quiet: bool,
    ):
        if await self.version_is_higher_than("5.7"):
            constraint_name = f"constraint_unique_{relationship_type}_{property_name}"
            if not quiet:
                stdout.write(
                    f" + Creating relationship unique constraint for {property_name} on relationship type {relationship_type} for relationship model {target_cls.__module__}.{relationship_cls.__name__}\n"
                )
            try:
                await self.cypher_query(
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
                f"Unique indexes on relationships are not supported in Neo4j version {await self.database_version}. Please upgrade to Neo4j 5.7 or higher."
            )

    async def _install_node(self, cls, name, property, quiet, stdout):
        # Create indexes and constraints for node property
        db_property = property.get_db_property_name(name)
        if property.index:
            await self._create_node_index(
                target_cls=cls, property_name=db_property, stdout=stdout, quiet=quiet
            )
        elif property.unique_index:
            await self._create_node_constraint(
                target_cls=cls, property_name=db_property, stdout=stdout, quiet=quiet
            )

        if property.fulltext_index:
            await self._create_node_fulltext_index(
                target_cls=cls,
                property_name=db_property,
                stdout=stdout,
                fulltext_index=property.fulltext_index,
                quiet=quiet,
            )

        if property.vector_index:
            await self._create_node_vector_index(
                target_cls=cls,
                property_name=db_property,
                stdout=stdout,
                vector_index=property.vector_index,
                quiet=quiet,
            )

    async def _install_relationship(self, cls, relationship, quiet, stdout):
        # Create indexes and constraints for relationship property
        relationship_cls = relationship.definition["model"]
        if relationship_cls is not None:
            relationship_type = relationship.definition["relation_type"]
            for prop_name, property in relationship_cls.defined_properties(
                aliases=False, rels=False
            ).items():
                db_property = property.get_db_property_name(prop_name)
                if property.index:
                    await self._create_relationship_index(
                        relationship_type=relationship_type,
                        target_cls=cls,
                        relationship_cls=relationship_cls,
                        property_name=db_property,
                        stdout=stdout,
                        quiet=quiet,
                    )
                elif property.unique_index:
                    await self._create_relationship_constraint(
                        relationship_type=relationship_type,
                        target_cls=cls,
                        relationship_cls=relationship_cls,
                        property_name=db_property,
                        stdout=stdout,
                        quiet=quiet,
                    )

                if property.fulltext_index:
                    await self._create_relationship_fulltext_index(
                        relationship_type=relationship_type,
                        target_cls=cls,
                        relationship_cls=relationship_cls,
                        property_name=db_property,
                        stdout=stdout,
                        fulltext_index=property.fulltext_index,
                        quiet=quiet,
                    )

                if property.vector_index:
                    await self._create_relationship_vector_index(
                        relationship_type=relationship_type,
                        target_cls=cls,
                        relationship_cls=relationship_cls,
                        property_name=db_property,
                        stdout=stdout,
                        vector_index=property.vector_index,
                        quiet=quiet,
                    )


# Create a singleton instance of the database object
adb = AsyncDatabase()


# Deprecated methods
async def change_neo4j_password(db: AsyncDatabase, user, new_password):
    deprecated(
        """
        This method has been moved to the Database singleton (db for sync, adb for async).
        Please use adb.change_neo4j_password(user, new_password) instead.
        This direct call will be removed in an upcoming version.
        """
    )
    await db.change_neo4j_password(user, new_password)


async def clear_neo4j_database(
    db: AsyncDatabase, clear_constraints=False, clear_indexes=False
):
    deprecated(
        """
        This method has been moved to the Database singleton (db for sync, adb for async).
        Please use adb.clear_neo4j_database(clear_constraints, clear_indexes) instead.
        This direct call will be removed in an upcoming version.
        """
    )
    await db.clear_neo4j_database(clear_constraints, clear_indexes)


async def drop_constraints(quiet=True, stdout=None):
    deprecated(
        """
        This method has been moved to the Database singleton (db for sync, adb for async).
        Please use adb.drop_constraints(quiet, stdout) instead.
        This direct call will be removed in an upcoming version.
        """
    )
    await adb.drop_constraints(quiet, stdout)


async def drop_indexes(quiet=True, stdout=None):
    deprecated(
        """
        This method has been moved to the Database singleton (db for sync, adb for async).
        Please use adb.drop_indexes(quiet, stdout) instead.
        This direct call will be removed in an upcoming version.
        """
    )
    await adb.drop_indexes(quiet, stdout)


async def remove_all_labels(stdout=None):
    deprecated(
        """
        This method has been moved to the Database singleton (db for sync, adb for async).
        Please use adb.remove_all_labels(stdout) instead.
        This direct call will be removed in an upcoming version.
        """
    )
    await adb.remove_all_labels(stdout)


async def install_labels(cls, quiet=True, stdout=None):
    deprecated(
        """
        This method has been moved to the Database singleton (db for sync, adb for async).
        Please use adb.install_labels(cls, quiet, stdout) instead.
        This direct call will be removed in an upcoming version.
        """
    )
    await adb.install_labels(cls, quiet, stdout)


async def install_all_labels(stdout=None):
    deprecated(
        """
        This method has been moved to the Database singleton (db for sync, adb for async).
        Please use adb.install_all_labels(stdout) instead.
        This direct call will be removed in an upcoming version.
        """
    )
    await adb.install_all_labels(stdout)


class AsyncTransactionProxy:
    bookmarks: Optional[Bookmarks] = None

    def __init__(self, db: AsyncDatabase, access_mode=None):
        self.db = db
        self.access_mode = access_mode

    @ensure_connection
    async def __aenter__(self):
        await self.db.begin(access_mode=self.access_mode, bookmarks=self.bookmarks)
        self.bookmarks = None
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        if exc_value:
            await self.db.rollback()

        if (
            exc_type is ClientError
            and exc_value.code == "Neo.ClientError.Schema.ConstraintValidationFailed"
        ):
            raise UniqueProperty(exc_value.message)

        if not exc_value:
            self.last_bookmark = await self.db.commit()

    def __call__(self, func):
        if AsyncUtil.is_async_code and not iscoroutinefunction(func):
            raise TypeError(NOT_COROUTINE_ERROR)

        @wraps(func)
        async def wrapper(*args, **kwargs):
            async with self:
                return await func(*args, **kwargs)

        return wrapper

    @property
    def with_bookmark(self):
        return BookmarkingAsyncTransactionProxy(self.db, self.access_mode)


class BookmarkingAsyncTransactionProxy(AsyncTransactionProxy):
    def __call__(self, func):
        if AsyncUtil.is_async_code and not iscoroutinefunction(func):
            raise TypeError(NOT_COROUTINE_ERROR)

        async def wrapper(*args, **kwargs):
            self.bookmarks = kwargs.pop("bookmarks", None)

            async with self:
                result = await func(*args, **kwargs)
                self.last_bookmark = None

            return result, self.last_bookmark

        return wrapper


class ImpersonationHandler:
    def __init__(self, db: AsyncDatabase, impersonated_user: str):
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


class NodeMeta(type):
    def __new__(mcs, name, bases, namespace):
        namespace["DoesNotExist"] = type(name + "DoesNotExist", (DoesNotExist,), {})
        cls = super().__new__(mcs, name, bases, namespace)
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


def build_class_registry(cls):
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
            if label_set not in adb._NODE_CLASS_REGISTRY:
                adb._NODE_CLASS_REGISTRY[label_set] = cls
            else:
                raise NodeClassAlreadyDefined(
                    cls, adb._NODE_CLASS_REGISTRY, adb._DB_SPECIFIC_CLASS_REGISTRY
                )
        else:
            for database in cls.__target_databases__:
                if database not in adb._DB_SPECIFIC_CLASS_REGISTRY:
                    adb._DB_SPECIFIC_CLASS_REGISTRY[database] = {}
                if label_set not in adb._DB_SPECIFIC_CLASS_REGISTRY[database]:
                    adb._DB_SPECIFIC_CLASS_REGISTRY[database][label_set] = cls
                else:
                    raise NodeClassAlreadyDefined(
                        cls, adb._NODE_CLASS_REGISTRY, adb._DB_SPECIFIC_CLASS_REGISTRY
                    )


NodeBase = NodeMeta("NodeBase", (AsyncPropertyManager,), {"__abstract_node__": True})


class AsyncStructuredNode(NodeBase):
    """
    Base class for all node definitions to inherit from.

    If you want to create your own abstract classes set:
        __abstract_node__ = True
    """

    # static properties

    __abstract_node__ = True

    # magic methods

    def __init__(self, *args, **kwargs):
        if "deleted" in kwargs:
            raise ValueError("deleted property is reserved for neomodel")

        for key, val in self.__all_relationships__:
            self.__dict__[key] = val.build_manager(self, key)

        super().__init__(*args, **kwargs)

    def __eq__(self, other: AsyncStructuredNode | Any) -> bool:
        """
        Compare two node objects.
        If both nodes were saved to the database, compare them by their element_id.
        Otherwise, compare them using object id in memory.
        If `other` is not a node, always return False.
        """
        if not isinstance(other, (AsyncStructuredNode,)):
            return False
        if self.was_saved and other.was_saved:
            return self.element_id == other.element_id
        return id(self) == id(other)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return f"<{self.__class__.__name__}: {self}>"

    def __str__(self):
        return repr(self.__properties__)

    # dynamic properties

    @classproperty
    def nodes(cls):
        """
        Returns a NodeSet object representing all nodes of the classes label
        :return: NodeSet
        :rtype: NodeSet
        """
        from neomodel.async_.match import AsyncNodeSet

        return AsyncNodeSet(cls)

    @property
    def element_id(self):
        if hasattr(self, "element_id_property"):
            return self.element_id_property
        return None

    # Version 4.4 support - id is deprecated in version 5.x
    @property
    def id(self):
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
    async def _build_merge_query(
        cls, merge_params, update_existing=False, lazy=False, relationship=None
    ):
        """
        Get a tuple of a CYPHER query and a params dict for the specified MERGE query.

        :param merge_params: The target node match parameters, each node must have a "create" key and optional "update".
        :type merge_params: list of dict
        :param update_existing: True to update properties of existing nodes, default False to keep existing values.
        :type update_existing: bool
        :rtype: tuple
        """
        query_params = dict(merge_params=merge_params)
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
            if not isinstance(relationship.source, AsyncStructuredNode):
                raise ValueError(
                    f"relationship source [{repr(relationship.source)}] is not a StructuredNode"
                )
            relation_type = relationship.definition.get("relation_type")
            if not relation_type:
                raise ValueError(
                    "No relation_type is specified on provided relationship"
                )

            from neomodel.async_.match import _rel_helper

            query_params["source_id"] = await adb.parse_element_id(
                relationship.source.element_id
            )
            query = f"MATCH (source:{relationship.source.__label__}) WHERE {await adb.get_id_method()}(source) = $source_id\n "
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
            query += f"RETURN {await adb.get_id_method()}(n)"
        else:
            query += "RETURN n"

        return query, query_params

    @classmethod
    async def create(cls, *props, **kwargs):
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
            query += f" RETURN {await adb.get_id_method()}(n)"
        else:
            query += " RETURN n"

        results = []
        for item in [
            cls.deflate(p, obj=_UnsavedNode(), skip_empty=True) for p in props
        ]:
            node, _ = await adb.cypher_query(query, {"create_params": item})
            results.extend(node[0])

        nodes = [cls.inflate(node) for node in results]

        if not lazy and hasattr(cls, "post_create"):
            for node in nodes:
                node.post_create()

        return nodes

    @classmethod
    async def create_or_update(cls, *props, **kwargs):
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
        lazy = kwargs.get("lazy", False)
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
        query, params = await cls._build_merge_query(
            create_or_update_params,
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
        results = await adb.cypher_query(query, params)
        return [cls.inflate(r[0]) for r in results[0]]

    async def cypher(self, query, params=None):
        """
        Execute a cypher query with the param 'self' pre-populated with the nodes neo4j id.

        :param query: cypher query string
        :type: string
        :param params: query parameters
        :type: dict
        :return: list containing query results
        :rtype: list
        """
        self._pre_action_check("cypher")
        params = params or {}
        element_id = await adb.parse_element_id(self.element_id)
        params.update({"self": element_id})
        return await adb.cypher_query(query, params)

    @hooks
    async def delete(self):
        """
        Delete a node and its relationships

        :return: True
        """
        self._pre_action_check("delete")
        await self.cypher(
            f"MATCH (self) WHERE {await adb.get_id_method()}(self)=$self DETACH DELETE self"
        )
        delattr(self, "element_id_property")
        self.deleted = True
        return True

    @classmethod
    async def get_or_create(cls, *props, **kwargs):
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
        query, params = await cls._build_merge_query(
            get_or_create_params, relationship=relationship, lazy=lazy
        )

        if "streaming" in kwargs:
            warnings.warn(
                STREAMING_WARNING,
                category=DeprecationWarning,
                stacklevel=1,
            )

        # fetch and build instance for each result
        results = await adb.cypher_query(query, params)
        return [cls.inflate(r[0]) for r in results[0]]

    @classmethod
    def inflate(cls, node):
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
    def inherited_labels(cls):
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
    def inherited_optional_labels(cls):
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

    async def labels(self):
        """
        Returns list of labels tied to the node from neo4j.

        :return: list of labels
        :rtype: list
        """
        self._pre_action_check("labels")
        result = await self.cypher(
            f"MATCH (n) WHERE {await adb.get_id_method()}(n)=$self " "RETURN labels(n)"
        )
        return result[0][0][0]

    def _pre_action_check(self, action):
        if hasattr(self, "deleted") and self.deleted:
            raise ValueError(
                f"{self.__class__.__name__}.{action}() attempted on deleted node"
            )
        if not hasattr(self, "element_id"):
            raise ValueError(
                f"{self.__class__.__name__}.{action}() attempted on unsaved node"
            )

    async def refresh(self):
        """
        Reload the node from neo4j
        """
        self._pre_action_check("refresh")
        if hasattr(self, "element_id"):
            results = await self.cypher(
                f"MATCH (n) WHERE {await adb.get_id_method()}(n)=$self RETURN n"
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
    async def save(self):
        """
        Save the node to neo4j or raise an exception

        :return: the node instance
        """

        # create or update instance node
        if hasattr(self, "element_id_property"):
            # update
            params = self.deflate(self.__properties__, self)
            query = f"MATCH (n) WHERE {await adb.get_id_method()}(n)=$self\n"

            if params:
                query += "SET "
                query += ",\n".join([f"n.{key} = ${key}" for key in params])
                query += "\n"
            if self.inherited_labels():
                query += "\n".join(
                    [f"SET n:`{label}`" for label in self.inherited_labels()]
                )
            await self.cypher(query, params)
        elif hasattr(self, "deleted") and self.deleted:
            raise ValueError(
                f"{self.__class__.__name__}.save() attempted on deleted node"
            )
        else:  # create
            result = await self.create(self.__properties__)
            created_node = result[0]
            self.element_id_property = created_node.element_id
        return self
