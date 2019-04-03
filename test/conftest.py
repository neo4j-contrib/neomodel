from __future__ import print_function
import warnings
import os
import sys

from neomodel import config, db, clear_neo4j_database, change_neo4j_password
from neo4j.v1 import CypherError


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
    
    config.DATABASE_URL = os.environ.get('NEO4J_BOLT_URL', 'bolt://neo4j:neo4j@localhost:7687')
    config.AUTO_INSTALL_LABELS = True
    
    try:
        # Clear the database if required
        database_is_populated, _ = db.cypher_query("MATCH (a) return count(a)>0 as database_is_populated")
        if database_is_populated[0][0] and not session.config.getoption("resetdb"):
            raise SystemError("Please note: The database seems to be populated.\n\tEither delete all nodes and edges manually, or set the --resetdb parameter when calling pytest\n\n\tpytest --resetdb.")
        else:
            clear_neo4j_database(db)        
    except CypherError as ce:
        # Handle instance without password being changed
        if 'The credentials you provided were valid, but must be changed before you can use this instance' in str(ce):
            warnings.warn("New database with no password set, setting password to 'test'")
            change_neo4j_password(db, 'test')
            db.set_connection('bolt://neo4j:test@localhost:7687')            
            warnings.warn("Please 'export NEO4J_BOLT_URL=bolt://neo4j:test@localhost:7687' for subsequent test runs")
        else:
            raise ce
