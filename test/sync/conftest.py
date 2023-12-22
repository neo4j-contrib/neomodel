import asyncio
import os
import warnings
from test._compat import mark_sync_session_auto_fixture

import pytest

from neomodel import config
from neomodel.sync_.core import db


@mark_sync_session_auto_fixture
def setup_neo4j_session(request, event_loop):
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
    database_is_populated, _ = db.cypher_query(
        "MATCH (a) return count(a)>0 as database_is_populated"
    )
    if database_is_populated[0][0] and not request.config.getoption("resetdb"):
        raise SystemError(
            "Please note: The database seems to be populated.\n\tEither delete all nodes and edges manually, or set the --resetdb parameter when calling pytest\n\n\tpytest --resetdb."
        )

    db.clear_neo4j_database(clear_constraints=True, clear_indexes=True)

    db.cypher_query(
        "CREATE OR REPLACE USER troygreene SET PASSWORD 'foobarbaz' CHANGE NOT REQUIRED"
    )
    if db.database_edition == "enterprise":
        db.cypher_query("GRANT ROLE publisher TO troygreene")
        db.cypher_query("GRANT IMPERSONATE (troygreene) ON DBMS TO admin")


@mark_sync_session_auto_fixture
def cleanup(event_loop):
    yield
    db.close_connection()


@pytest.fixture(scope="session")
def event_loop():
    """Overrides pytest default function scoped event loop"""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()
