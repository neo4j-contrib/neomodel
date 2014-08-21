from __future__ import print_function
import warnings
from neomodel.core import db
warnings.simplefilter('default')
db.new_session()
db.session.clear()
print("neo4j version: ", *db.session.neo4j_version)
