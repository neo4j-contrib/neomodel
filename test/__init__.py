from __future__ import print_function
import warnings
from neomodel.core import db
warnings.simplefilter('default')
db.cypher_query("MATCH (a) DETACH DELETE a")
