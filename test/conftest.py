from __future__ import print_function
import warnings
import os

from neomodel import config, db, clear_neo4j_database, change_neo4j_password
from neo4j.v1 import CypherError

warnings.simplefilter('default')

config.DATABASE_URL = os.environ.get('NEO4J_BOLT_URL', 'bolt://neo4j:neo4j@localhost:7687')
config.AUTO_INSTALL_LABELS = True

try:
    clear_neo4j_database(db)
except CypherError as ce:
    # handle instance without password being changed
    if 'The credentials you provided were valid, but must be changed before you can use this instance' in str(ce):
        change_neo4j_password(db, 'test')
        db.set_connection('bolt://neo4j:test@localhost:7687')

        print("New database with no password set, setting password to 'test'")
        print("Please 'export NEO4J_BOLT_URL=bolt://neo4j:test@localhost:7687' for subsequent test runs")
    else:
        raise ce
