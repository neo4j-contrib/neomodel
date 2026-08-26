"""
Query execution for the async neomodel module.

``AsyncQueryRunner`` runs Cypher (in the active transaction or an auto-commit
session), streams results, and resolves returned graph objects to neomodel
classes via the standalone registry. It operates against an
``AsyncConnectionManager`` held as ``self.db``.
"""

import logging
import time
from typing import Any, AsyncIterator

from neo4j import AsyncResult, AsyncSession, AsyncTransaction, Query
from neo4j.exceptions import ClientError, SessionExpired
from neo4j.graph import Node, Path, Relationship

from neomodel.async_._registry import registry
from neomodel.async_.connection import AsyncConnectionManager, ensure_connection
from neomodel.config import get_config
from neomodel.exceptions import (
    ConstraintValidationFailed,
    NodeClassNotDefined,
    RelationshipClassNotDefined,
    UniqueProperty,
)

logger = logging.getLogger(__name__)

# Substrings that mark a query-parameter key as sensitive. Keys are normalised
# to lowercase alphanumerics before matching, so compound and differently-styled
# names such as "user_password", "stripe_api_key", "refresh_token" or
# "accessKey" are all caught. This is a best-effort default; applications with
# their own naming conventions should configure
# ``config.cypher_log_redaction_hook``.
SENSITIVE_PARAM_KEY_SUBSTRINGS = frozenset(
    {
        "password",
        "passwd",
        "passphrase",
        "secret",
        "token",
        "apikey",
        "privatekey",
        "credential",
        "authorization",
        "accesskey",
        "sessionkey",
        "encryptionkey",
    }
)

# Short or ambiguous names that are only treated as sensitive on an exact
# (normalised) match, to avoid false positives from substring matching such as
# "author" (auth), "passenger" (pass) or "monkey" (key).
SENSITIVE_PARAM_KEYS = frozenset(
    {
        "pwd",
        "pass",
        "auth",
        "key",
        "otp",
        "totp",
        "mfa",
        "pin",
        "ssn",
        "cvv",
        "cvc",
    }
)


def _is_sensitive_param_key(key: Any) -> bool:
    """Return True if a query-parameter key looks like it carries a secret."""
    normalized = "".join(char for char in str(key).lower() if char.isalnum())
    if normalized in SENSITIVE_PARAM_KEYS:
        return True
    return any(token in normalized for token in SENSITIVE_PARAM_KEY_SUBSTRINGS)


def _redact_params(params: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return a copy of ``params`` suitable for logging.

    Query parameters may contain sensitive data (PII, secrets, password hashes,
    whatever the application stores). If a custom redaction hook is configured
    via ``config.cypher_log_redaction_hook`` it is applied; otherwise the values
    of keys that look sensitive (see :func:`_is_sensitive_param_key`) are masked.
    """
    if not params:
        return params
    hook = getattr(get_config(), "cypher_log_redaction_hook", None)
    if hook is not None:
        return hook(params)
    return {
        key: ("******" if _is_sensitive_param_key(key) else value)
        for key, value in params.items()
    }


def _log_slow_query(query: str, params: dict[str, Any] | None, tte: float) -> None:
    """Log a query and its (redacted) parameters when Cypher debug logging is on.

    Driven by ``config.cypher_debug`` / ``config.slow_queries`` (populated from
    NEOMODEL_CYPHER_DEBUG / NEOMODEL_SLOW_QUERIES) rather than reading the
    environment on every query.
    """
    config = get_config()
    if config.cypher_debug and tte > config.slow_queries:
        logger.debug(
            "query: "
            + query
            + "\nparams: "
            + repr(_redact_params(params))
            + f"\ntook: {tte:.2g}s\n"
        )


# Phrases Neo4j uses to describe a uniqueness-constraint violation. The wording
# depends on the server version and on how the violating write happened: an
# inline ``CREATE (n:Label {...})`` reports "... already exists with label ...",
# whereas a ``SET`` (used by batch create()'s UNWIND ... SET, and by 4.x servers
# generally) reports "... share the property value ...". Both mean the same
# thing and should surface as UniqueProperty.
_UNIQUE_VIOLATION_MARKERS = (
    "already exists with label",
    "share the property value",
)


def _is_unique_constraint_violation(message: str) -> bool:
    return any(marker in message for marker in _UNIQUE_VIOLATION_MARKERS)


class AsyncQueryRunner:
    """Runs Cypher and resolves results against a connection manager."""

    def __init__(self, connection: AsyncConnectionManager) -> None:
        # Named ``db`` so the ``ensure_connection`` decorator resolves the
        # connection state through ``self.db``.
        self.db: AsyncConnectionManager = connection

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
            node_class = registry.get_class(_labels, self.db._database_name)
            if node_class is not None:
                return node_class.inflate(object_to_resolve)
            raise NodeClassNotDefined(
                object_to_resolve,
                registry.snapshot_node_registry(),
                registry.snapshot_db_registry(),
            )

        if isinstance(object_to_resolve, Relationship):
            rel_type = frozenset([object_to_resolve.type])
            rel_class = registry.get_class(rel_type, self.db._database_name)
            if rel_class is not None:
                return rel_class.inflate(object_to_resolve)
            raise RelationshipClassNotDefined(
                object_to_resolve,
                registry.snapshot_node_registry(),
                registry.snapshot_db_registry(),
            )

        if isinstance(object_to_resolve, Path):
            from neomodel.async_.path import AsyncNeomodelPath

            return AsyncNeomodelPath(object_to_resolve)

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
    async def cypher_query(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        handle_unique: bool = True,
        retry_on_session_expire: bool = False,
        resolve_objects: bool = False,
    ) -> tuple[list, tuple[str, ...]]:
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
        if self.db._active_transaction:
            # Use current transaction if a transaction is currently active
            results, meta = await self._run_cypher_query(
                self.db._active_transaction,
                query,
                params,
                handle_unique,
                retry_on_session_expire,
                resolve_objects,
            )
        else:
            # Otherwise create a new session in a with to dispose of it after it has been run
            if self.db.driver:
                async with self.db.driver.session(
                    database=self.db._database_name,
                    impersonated_user=self.db.impersonated_user,
                ) as session:
                    results, meta = await self._run_cypher_query(
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

    @staticmethod
    def _build_run_query(
        session: AsyncSession | AsyncTransaction, query: str
    ) -> str | Query:
        """
        Wrap the query so the configured transaction timeout applies to auto-commit
        queries. The driver only accepts a timeout on session.run; queries running in
        an explicit transaction inherit the timeout given to begin_transaction.
        """
        timeout = get_config().transaction_timeout
        if timeout is not None and isinstance(session, AsyncSession):
            return Query(query, timeout=timeout)
        return query

    async def _run_cypher_query(
        self,
        session: AsyncSession | AsyncTransaction,
        query: str,
        params: dict[str, Any],
        handle_unique: bool,
        retry_on_session_expire: bool,
        resolve_objects: bool,
    ) -> tuple[list, tuple[str, ...]]:
        try:
            # Retrieve the data
            start = time.time()
            if self.db._parallel_runtime:
                query = "CYPHER runtime=parallel " + query
            # _build_run_query only wraps in Query for auto-commit sessions (never
            # transactions), but mypy cannot correlate that with the session type here.
            response: AsyncResult = await session.run(
                query=self._build_run_query(session, query),  # type: ignore[arg-type]
                parameters=params,
            )
            results, meta = [list(r.values()) async for r in response], response.keys()
            end = time.time()

            if resolve_objects:
                # Do any automatic resolution required
                results = self._result_resolution(results)

        except ClientError as e:
            if e.code == "Neo.ClientError.Schema.ConstraintValidationFailed":
                if hasattr(e, "message") and e.message is not None:
                    if _is_unique_constraint_violation(e.message) and handle_unique:
                        raise UniqueProperty(e.message) from e
                    raise ConstraintValidationFailed(e.message) from e
                raise ConstraintValidationFailed(
                    "A constraint validation failed"
                ) from e

            # Any other ClientError propagates unchanged (with its traceback).
            raise
        except SessionExpired:
            if retry_on_session_expire:
                await self.db.set_connection(url=self.db._connection_url)
                return await self.cypher_query(
                    query=query,
                    params=params,
                    handle_unique=handle_unique,
                    retry_on_session_expire=False,
                )
            raise

        tte = end - start
        _log_slow_query(query, params, tte)

        return results, meta

    async def _stream_cypher_query(
        self,
        session: AsyncSession | AsyncTransaction,
        query: str,
        params: dict[str, Any],
        handle_unique: bool,
        resolve_objects: bool,
    ) -> AsyncIterator[tuple[list, tuple[str, ...]]]:
        """
        Stream query results one record at a time without loading all into memory.

        This is an internal method used for async iteration. It yields results
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
            if self.db._parallel_runtime:
                query = "CYPHER runtime=parallel " + query

            # _build_run_query only wraps in Query for auto-commit sessions (never
            # transactions), but mypy cannot correlate that with the session type here.
            response: AsyncResult = await session.run(
                query=self._build_run_query(session, query),  # type: ignore[arg-type]
                parameters=params,
            )
            keys = response.keys()

            # Stream results one record at a time
            async for record in response:
                values = list(record.values())

                if resolve_objects:
                    # Resolve objects for this single record
                    for idx, value in enumerate(values):
                        values[idx] = self._object_resolution(value)

                yield values, keys

            end = time.time()
            tte = end - start
            _log_slow_query(query, params, tte)

        except ClientError as e:
            if e.code == "Neo.ClientError.Schema.ConstraintValidationFailed":
                if hasattr(e, "message") and e.message is not None:
                    if _is_unique_constraint_violation(e.message) and handle_unique:
                        raise UniqueProperty(e.message) from e
                    raise ConstraintValidationFailed(e.message) from e
                raise ConstraintValidationFailed(
                    "A constraint validation failed"
                ) from e

            # Any other ClientError propagates unchanged (with its traceback).
            raise
