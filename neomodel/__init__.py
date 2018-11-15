# pep8: noqa
import pkg_resources
from .core import *
from neomodel.exceptions import *
from .util import clear_neo4j_database, change_neo4j_password
from neomodel.match import EITHER, INCOMING, OUTGOING, NodeSet, Traversal
from neomodel.match_q import Q  # noqa
from neomodel.relationship_manager import (
    NotConnected, RelationshipTo, RelationshipFrom, Relationship,
    RelationshipManager, RelationshipDefinition
)
from .relationship import StructuredRel
from .cardinality import (ZeroOrMore, OneOrMore, ZeroOrOne, One)
from .properties import (StringProperty, IntegerProperty, AliasProperty,
                         FloatProperty, BooleanProperty, DateTimeProperty, DateProperty,
                         NormalizedProperty, RegexProperty, EmailProperty,
                         JSONProperty, ArrayProperty, UniqueIdProperty)


# If shapely is not installed, its import will fail and the spatial properties will not be available
try:
    from .spatial_properties import (NeomodelPoint,PointProperty)
except ImportError:
    sys.stderr.write('WARNING: Shapely not found on system, spatial capabilities will not be available.\n'
                     'If required, you can install Shapely via `pip install shapely`.')

                         
__author__ = 'Robin Edwards'
__email__ = 'robin.ge@gmail.com'
__license__ = 'MIT'
__package__ = 'neomodel'
__version__ = pkg_resources.get_distribution('neomodel').version
