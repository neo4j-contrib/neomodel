import os
import warnings
from test._async_compat import (
    mark_async_function_auto_fixture,
    mark_async_session_auto_fixture,
)

from neomodel import adb, config


@mark_async_session_auto_fixture
async def setup_neo4j_session(request):
    """
    Provides initial connection to the database and sets up the rest of the test suite

    :param request: The request object. Please see <https://docs.pytest.org/en/latest/reference.html#_pytest.hookspec.pytest_sessionstart>`_
    :type Request object: For more information please see <https://docs.pytest.org/en/latest/reference.html#request>`_
    """

    warnings.simplefilter("default")

    config.DATABASE_URL = os.environ.get(
        "NEO4J_BOLT_URL", "bolt://neo4j:foobarbaz@localhost:7687"
    )

    # Clear the database if required
    database_is_populated, _ = await adb.cypher_query(
        "MATCH (a) return count(a)>0 as database_is_populated"
    )
    if database_is_populated[0][0] and not request.config.getoption("resetdb"):
        raise SystemError(
            "Please note: The database seems to be populated.\n\tEither delete all nodes and edges manually, or set the --resetdb parameter when calling pytest\n\n\tpytest --resetdb."
        )

    await adb.clear_neo4j_database(clear_constraints=True, clear_indexes=True)

    await adb.install_all_labels()

    await adb.cypher_query(
        "CREATE OR REPLACE USER troygreene SET PASSWORD 'foobarbaz' CHANGE NOT REQUIRED"
    )
    db_edition = await adb.database_edition
    if db_edition == "enterprise":
        await adb.cypher_query("GRANT ROLE publisher TO troygreene")
        await adb.cypher_query("GRANT IMPERSONATE (troygreene) ON DBMS TO admin")

    yield

    await adb.close_connection()


@mark_async_function_auto_fixture
async def setUp():
    await adb.cypher_query("MATCH (n) DETACH DELETE n")
    yield
