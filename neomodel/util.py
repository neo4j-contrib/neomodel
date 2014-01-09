from py2neo import neo4j
from py2neo.exceptions import ClientError
from .exception import CypherException, UniqueProperty
import time
import os
import logging
logger = logging.getLogger(__name__)


class Node(object):
    def __init__(self, data):
        self._id = int(neo4j.URI(data['self']).path.segments[-1])
        self._properties = data.get('data', {})


class Rel(object):
    def __init__(self, data):
        self._id = int(neo4j.URI(data['self']).path.segments[-1])
        self._properties = data.get('data', {})
        self._type = data['type']


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
        if (handle_unique and e.exception == 'CypherExecutionException' and
                " already exists with label " in e.message and e.message.startswith('Node ')):
            raise UniqueProperty(e.message)

        raise CypherException(query, params, e.message, e.exception, e.stack_trace)

    if os.environ.get('NEOMODEL_CYPHER_DEBUG', False):
        logger.debug("query: " + query + "\nparams: " + repr(params) + "\ntook: %.2gs\n" % (end - start))

    return results
