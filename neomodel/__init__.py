# pep8: noqa
import pkg_resources

from neomodel.exceptions import *
from neomodel.match import EITHER, INCOMING, OUTGOING, NodeSet, Traversal
from neomodel.match_q import Q  # noqa
from neomodel.relationship_manager import (
    NotConnected,
    Relationship,
    RelationshipDefinition,
    RelationshipFrom,
    RelationshipManager,
    RelationshipTo,
)

from .cardinality import One, OneOrMore, ZeroOrMore, ZeroOrOne
from .core import *
from .properties import (
    AliasProperty,
    ArrayProperty,
    BooleanProperty,
    DateProperty,
    DateTimeFormatProperty,
    DateTimeProperty,
    EmailProperty,
    FloatProperty,
    IntegerProperty,
    JSONProperty,
    NormalizedProperty,
    RegexProperty,
    StringProperty,
    UniqueIdProperty,
)
from .relationship import StructuredRel
from .util import change_neo4j_password, clear_neo4j_database

__author__ = "Robin Edwards"
__email__ = "robin.ge@gmail.com"
__license__ = "MIT"
__package__ = "neomodel"
__version__ = "5.0.1"
