import logging
import os
import time
import warnings
import sys
from threading import local
from py2neo import neo4j
from py2neo.exceptions import ClientError
from py2neo.packages.httpstream import SocketError
from .exception import CypherException, UniqueProperty

if sys.version_info >= (3, 0):
    from urllib.parse import urlparse
else:
    from urlparse import urlparse  # noqa

logger = logging.getLogger(__name__)

path_to_id = lambda val: int(neo4j.URI(val).path.segments[-1])


class Node(object):
    def __init__(self, data):
        self._id = path_to_id(data['self'])
        self._properties = data.get('data', {})


class Rel(object):
    def __init__(self, data):
        self._id = path_to_id(data['self'])
        self._properties = data.get('data', {})
        self._type = data['type']
        self._start_node_id = path_to_id(data['start'])
        self._end_node_id = path_to_id(data['end'])


def _hydrated(data):
    if isinstance(data, dict):
        if 'self' in data:
            obj_type = neo4j.URI(data['self']).path.segments[-2]
            if obj_type == 'node':
                return Node(data)
            elif obj_type == 'relationship':
                return Rel(data)
        raise NotImplemented("Don't know how to inflate: " + repr(data))
    elif neo4j.is_collection(data):
        return type(data)([_hydrated(datum) for datum in data])
    else:
        return data

neo4j._hydrated = _hydrated


class Database(local):
    def __init__(self, _url):
        if hasattr(self, 'session'):
            raise SystemError('__init__ called too many times')

        u = urlparse(_url)
        if u.netloc.find('@') > -1:
            credentials, self.host = u.netloc.split('@')
            self.user, self.password, = credentials.split(':')
            self.url = ''.join([u.scheme, '://', self.host, u.path, u.query])
            neo4j.authenticate(self.host, self.user, self.password)
        else:
            self.url = _url

    def new_session(self):
        try:
            self.session = neo4j.GraphDatabaseService(self.url)
        except SocketError as e:
            raise SocketError("Error connecting to {0} - {1}".format(self.url, e))

        if self.session.neo4j_version < (2, 0):
            raise Exception("Support for neo4j versions prior to 2.0 are "
                    + "supported by the 0.x.x series releases of neomodel")

    def cypher_query(self, query, params=None, handle_unique=True):
        try:
            cq = neo4j.CypherQuery(self.session, '')
            start = time.clock()
            result = neo4j.CypherResults(cq._cypher._post({'query': query, 'params': params or {}}))
            end = time.clock()
            results = result.data, list(result.columns)
        except ClientError as e:
            if (handle_unique and e.exception == 'CypherExecutionException' and
                    " already exists with label " in e.message and e.message.startswith('Node ')):
                raise UniqueProperty(e.message)

            raise CypherException(query, params, e.message, e.exception, e.stack_trace)

        if os.environ.get('NEOMODEL_CYPHER_DEBUG', False):
            logger.debug("query: " + query + "\nparams: " + repr(params) + "\ntook: %.2gs\n" % (end - start))

        return results


def deprecated(message):
    def f__(f):
        def f_(*args, **kwargs):
            warnings.warn(message, category=DeprecationWarning, stacklevel=2)
            return f(*args, **kwargs)
        f_.__name__ = f.__name__
        f_.__doc__ = f.__doc__
        f_.__dict__.update(f.__dict__)
        return f_
    return f__


def classproperty(f):
    class cpf(object):
        def __init__(self, getter):
            self.getter = getter

        def __get__(self, obj, type=None):
            return self.getter(type)
    return cpf(f)
