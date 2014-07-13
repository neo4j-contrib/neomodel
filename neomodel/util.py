import logging
import os
import time
import warnings
from py2neo import neo4j
from py2neo.exceptions import ClientError
from .exception import CypherException, UniqueProperty
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


def cypher_query(connection, query, params=None, handle_unique=True):
    if hasattr(query, '__str__'):
        query = query.__str__()

    try:
        cq = neo4j.CypherQuery(connection, '')
        start = time.clock()
        result = neo4j.CypherResults(cq._cypher._post({'query': query, 'params': params or {}}))
        end = time.clock()
        results = result.data, list(result.columns)
    except ClientError as e:
        errorstr = str(e)
        if (handle_unique and e.exception == 'CypherExecutionException' and
                " already exists with label " in errorstr and errorstr.startswith('Node ')):
            raise UniqueProperty(errorstr)

        raise CypherException(query, params, errorstr, e.exception, e.stack_trace)

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
