from .exception import PropertyNotIndexed
from .properties import AliasProperty
from .util import items
from py2neo import neo4j
import sys
import re


if sys.version_info >= (3, 0):
    unicode = lambda x: str(x)

# http://fragmentsofcode.wordpress.com/2010/03/10/escape-special-characters-for-solrlucene-query/
ESCAPE_CHARS_RE = re.compile(r'(?<!\\)(?P<char>[&|+\-!(){}[\]^"~*?:])')
lucene_esc = lambda v: ESCAPE_CHARS_RE.sub(r'\\\g<char>', unicode(v))


class NodeIndexManager(object):
    def __init__(self, node_class, index_name):
        self.node_class = node_class
        self.name = index_name

    def _check_params(self, params):
        """checked args are indexed and convert aliases"""
        for key in params.keys():
            prop = self.node_class.get_property(key)
            if not prop.is_indexed:
                raise PropertyNotIndexed(key)
            if isinstance(prop, AliasProperty):
                real_key = prop.aliased_to()
                if real_key in params:
                    msg = "Can't alias {0} to {1} in {2}, key {0} exists."
                    raise Exception(msg.format(key, real_key, repr(params)))
                params[real_key] = params[key]
                del params[key]

    def _execute(self, query):
        return self.__index__.query(query)

    def search(self, query=None, **kwargs):
        """ Load multiple nodes via index """
        if not query:
            self._check_params(kwargs)
            query = ','.join([k + ':' + lucene_esc(v) for k, v in items(kwargs)])

        return [self.node_class.inflate(n) for n in self._execute(str(query))]

    def get(self, query=None, **kwargs):
        """ Load single node via index """
        nodes = self.search(query=query, **kwargs)
        if len(nodes) == 1:
            return nodes[0]
        elif len(nodes) > 1:
            raise Exception("Multiple nodes returned from query, expected one")
        else:
            raise self.node_class.DoesNotExist("Can't find node in index matching query")

    @property
    def __index__(self):
        from .core import connection
        return connection().get_or_create_index(neo4j.Node, self.name)
