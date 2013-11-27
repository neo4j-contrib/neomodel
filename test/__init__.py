from __future__ import print_function
import warnings
from neomodel.core import connection
warnings.simplefilter('default')
connection().clear()
print("neo4j version: ", *connection().neo4j_version)
