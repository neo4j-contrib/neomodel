from __future__ import print_function
import warnings
import os
import sys

import pytest

from neomodel import config, db, clear_neo4j_database, change_neo4j_password
from neo4j.exceptions import ClientError as CypherError
from neobolt.exceptions import ClientError


def pytest_addoption(parser):
    """
    Adds the command line option --resetdb.
    
    :param parser: The parser object. Please see <https://docs.pytest.org/en/latest/reference.html#_pytest.hookspec.pytest_addoption>`_
    :type Parser object: For more information please see <https://docs.pytest.org/en/latest/reference.html#_pytest.config.Parser>`_
    """
    parser.addoption("--resetdb", action="store_true", help = "Ensures that the database is clear prior to running tests for neomodel", default=False)
    

def pytest_sessionstart(session):
    """
    Provides initial connection to the database and sets up the rest of the test suite
    
    :param session: The session object. Please see <https://docs.pytest.org/en/latest/reference.html#_pytest.hookspec.pytest_sessionstart>`_
    :type Session object: For more information please see <https://docs.pytest.org/en/latest/reference.html#session>`_
    """
    
    warnings.simplefilter('default')
    
    config.DATABASE_URL = os.environ.get('NEO4J_BOLT_URL', 'bolt://neo4j:foobarbaz@localhost:7687')
    config.AUTO_INSTALL_LABELS = True
    
    try:
        # Clear the database if required
        database_is_populated, _ = db.cypher_query("MATCH (a) return count(a)>0 as database_is_populated")
        if database_is_populated[0][0] and not session.config.getoption("resetdb"):
            raise SystemError("Please note: The database seems to be populated.\n\tEither delete all nodes and edges manually, or set the --resetdb parameter when calling pytest\n\n\tpytest --resetdb.")
        else:
            clear_neo4j_database(db, clear_constraints=True, clear_indexes=True)        
    except (CypherError, ClientError) as ce:
        # Handle instance without password being changed
        if 'The credentials you provided were valid, but must be changed before you can use this instance' in str(ce):
            warnings.warn("New database with no password set, setting password to 'test'")
            try:
                change_neo4j_password(db, 'test')
                # Ensures that multiprocessing tests can use the new password
                config.DATABASE_URL = 'bolt://neo4j:test@localhost:7687'
                db.set_connection('bolt://neo4j:test@localhost:7687')
                warnings.warn("Please 'export NEO4J_BOLT_URL=bolt://neo4j:test@localhost:7687' for subsequent test runs")
            except (CypherError, ClientError) as e:
                if 'The credentials you provided were valid, but must be changed before you can use this instance' in str(e):
                    warnings.warn("You appear to be running on version 4.0+ of Neo4j, without having changed the password."
                        "Please manually log in, change your password, then update the config.DATABASE_URL call at line 32 in this file")
                else:
                    raise e
        else:
            raise ce


def version_to_dec(a_version_string):
    """
    Converts a version string to a number to allow for quick checks on the versions of specific components.

    :param a_version_string: The version string under test (e.g. '3.4.0')
    :type a_version_string: str
    :return: An integer representation of the string version, e.g. '3.4.0' --> 340
    """
    components = a_version_string.split('.')
    while len(components) < 3:
        components.append('0')
    num = 0
    for a_component in enumerate(components):
        num += (10 ** ((len(components) - 1) - a_component[0])) * int(a_component[1])
    return num


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
    if 'NEO4J_VERSION' in os.environ:
        if version_to_dec(os.environ['NEO4J_VERSION']) < required_least_neo4j_version:
            pytest.skip('Neo4j version: {}. {}.'
                        'Skipping test.'.format(os.environ['NEO4J_VERSION'], message))

@pytest.fixture
def skip_neo4j_before_330():
    check_and_skip_neo4j_least_version(330, 'Neo4J version does not support this test')
