from __future__ import print_function

import os
import warnings

import pytest

from neomodel import clear_neo4j_database, config, db
from neomodel.util import version_tag_to_integer

NEO4J_URL = os.environ.get("NEO4J_URL", "bolt://localhost:7687")
NEO4J_USERNAME = os.environ.get("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "foobarbaz")


def pytest_addoption(parser):
    """
    Adds the command line option --resetdb.

    :param parser: The parser object. Please see <https://docs.pytest.org/en/latest/reference.html#_pytest.hookspec.pytest_addoption>`_
    :type Parser object: For more information please see <https://docs.pytest.org/en/latest/reference.html#_pytest.config.Parser>`_
    """
    parser.addoption(
        "--resetdb",
        action="store_true",
        help="Ensures that the database is clear prior to running tests for neomodel",
        default=False,
    )


@pytest.hookimpl
def pytest_collection_modifyitems(items):
    connect_to_aura_items = []
    normal_items = []

    # Separate all tests into two groups: those with "connect_to_aura" in their name, and all others
    for item in items:
        if "connect_to_aura" in item.name:
            connect_to_aura_items.append(item)
        else:
            normal_items.append(item)

    # Add all normal tests back to the front of the list
    new_order = normal_items

    # Add all connect_to_aura tests to the end of the list
    new_order.extend(connect_to_aura_items)

    # Replace the original items list with the new order
    items[:] = new_order


@pytest.hookimpl
def pytest_sessionstart(session):
    """
    Provides initial connection to the database and sets up the rest of the test suite

    :param session: The session object. Please see <https://docs.pytest.org/en/latest/reference.html#_pytest.hookspec.pytest_sessionstart>`_
    :type Session object: For more information please see <https://docs.pytest.org/en/latest/reference.html#session>`_
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
    if database_is_populated[0][0] and not session.config.getoption("resetdb"):
        raise SystemError(
            "Please note: The database seems to be populated.\n\tEither delete all nodes and edges manually, or set the --resetdb parameter when calling pytest\n\n\tpytest --resetdb."
        )
    else:
        clear_neo4j_database(db, clear_constraints=True, clear_indexes=True)

    db.cypher_query(
        "CREATE OR REPLACE USER troygreene SET PASSWORD 'foobarbaz' CHANGE NOT REQUIRED"
    )
    if db.database_edition == "enterprise":
        db.cypher_query("GRANT ROLE publisher TO troygreene")
        db.cypher_query("GRANT IMPERSONATE (troygreene) ON DBMS TO admin")


@pytest.hookimpl
def pytest_unconfigure():
    db.close_connection()


def check_and_skip_neo4j_least_version(required_least_neo4j_version, message):
    """
    Checks if the NEO4J_VERSION is at least `required_least_neo4j_version` and skips a test if not.

    WARNING: If the NEO4J_VERSION variable is not set, this function returns True, allowing the test to go ahead.

    :param required_least_neo4j_version: The least version to check. This must be the numberic representation of the
    version. That is: '3.4.0' would be passed as 340.
    :type required_least_neo4j_version: int
    :param message: An informative message as to why the calling test had to be skipped.
    :type message: str
    :return: A boolean value of True if the version reported is at least `required_least_neo4j_version`
    """
    if (
        "NEO4J_VERSION" in os.environ
        and version_tag_to_integer(os.environ["NEO4J_VERSION"])
        < required_least_neo4j_version
    ):
        pytest.skip(
            "Neo4j version: {}. {}."
            "Skipping test.".format(os.environ["NEO4J_VERSION"], message)
        )


@pytest.fixture
def skip_neo4j_before_330():
    check_and_skip_neo4j_least_version(330, "Neo4J version does not support this test")
