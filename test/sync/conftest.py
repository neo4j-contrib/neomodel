import asyncio
import os
import warnings
from test._async_compat import mark_async_test

import pytest
import pytest_asyncio

from neomodel import config
from neomodel._async.core import adb


@pytest_asyncio.fixture(scope="session", autouse=True)
@mark_async_test
def setup_neo4j_session(request):
    """
    Provides initial connection to the database and sets up the rest of the test suite

    :param request: The request object. Please see <https://docs.pytest.org/en/latest/reference.html#_pytest.hookspec.pytest_sessionstart>`_
    :type Request object: For more information please see <https://docs.pytest.org/en/latest/reference.html#request>`_
    """

    warnings.simplefilter("default")

    config.DATABASE_URL = os.environ.get(
        "NEO4J_BOLT_URL", "bolt://neo4j:foobarbaz@localhost:7687"
    )
    config.AUTO_INSTALL_LABELS = True

    # Clear the database if required
    database_is_populated, _ = adb.cypher_query_async(
        "MATCH (a) return count(a)>0 as database_is_populated"
    )
    if database_is_populated[0][0] and not request.config.getoption("resetdb"):
        raise SystemError(
            "Please note: The database seems to be populated.\n\tEither delete all nodes and edges manually, or set the --resetdb parameter when calling pytest\n\n\tpytest --resetdb."
        )

    adb.clear_neo4j_database_async(clear_constraints=True, clear_indexes=True)

    adb.cypher_query_async(
        "CREATE OR REPLACE USER troygreene SET PASSWORD 'foobarbaz' CHANGE NOT REQUIRED"
    )
    if adb.database_edition == "enterprise":
        adb.cypher_query_async("GRANT ROLE publisher TO troygreene")
        adb.cypher_query_async("GRANT IMPERSONATE (troygreene) ON DBMS TO admin")


@pytest_asyncio.fixture(scope="session", autouse=True)
@mark_async_test
def cleanup():
    yield
    adb.close_connection_async()


@pytest.fixture(scope="session")
def event_loop():
    """Overrides pytest default function scoped event loop"""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()
