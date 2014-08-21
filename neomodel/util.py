import logging
import os
import time
import warnings
import sys
from threading import local
from py2neo import neo4j
from py2neo.exceptions import ClientError
from py2neo.packages.httpstream import SocketError
from py2neo import cypher as py2neo_cypher
from .exception import CypherException, UniqueProperty, TransactionError
if sys.version_info >= (3, 0):
    from urllib.parse import urlparse
else:
    from urlparse import urlparse  # noqa

logger = logging.getLogger(__name__)

path_to_id = lambda val: int(neo4j.URI(val).path.segments[-1])


class PatchedTransaction(py2neo_cypher.Transaction):
    def __init__(self, uri):
        super(PatchedTransaction, self).__init__(uri)

    def _post(self, resource):
        self._assert_unfinished()
        rs = resource._post({"statements": self._statements})
        location = dict(rs.headers).get("location")
        if location:
            self._execute = py2neo_cypher.Resource(location)
        j = rs.json
        rs.close()
        self._clear()
        if "commit" in j:
            self._commit = py2neo_cypher.Resource(j["commit"])
        if "errors" in j and len(j['errors']):
            error = j["errors"][0]
            txid = int(j['commit'].split('/')[-2])
            trace = error.get('stackTrace', error.get('stacktrace', ''))
            raise TransactionError(error['message'], error['code'], trace, txid)
        out = []
        for result in j["results"]:
            producer = py2neo_cypher.RecordProducer(result["columns"])
            out.append([
                producer.produce(_hydrated(r["rest"]))
                for r in result["data"]
            ])
        return out


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
py2neo_cypher._hydrated = _hydrated
py2neo_cypher.Transaction = PatchedTransaction


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

        if hasattr(self, 'tx_session'):
            delattr(self, 'tx_session')

    @property
    def transaction(self):
        db = self

        class TX(object):
            def __call__(s, func):

                def wrapper(*args, **kwargs):
                    db.begin()
                    try:
                        r = func(*args)
                    except (ClientError, UniqueProperty, TransactionError):
                        # error from database so don't rollback
                        exc_info = sys.exc_info()
                        db.new_session()

                        if sys.version_info >= (3, 0):
                            raise exc_info[1].with_traceback(exc_info[2])
                        else:
                            raise exc_info[1]
                    except Exception:
                        exc_info = sys.exc_info()
                        db.rollback()
                        raise exc_info[1]
                    db.commit()
                    return r

                return wrapper

            def __enter__(self):
                db.begin()

            def __exit__(self, exception_type, exception_value, traceback):
                if not all([exception_type, exception_value, traceback]):
                    return db.commit()

                if isinstance(exception_value, (ClientError, UniqueProperty, TransactionError)):
                    # error from database so don't rollback
                    db.new_session()
                else:
                    db.rollback()
        return TX()

    def begin(self):
        if hasattr(self, 'tx_session'):
            raise SystemError("Transaction already in progress")

        self.tx_session = py2neo_cypher.Session(self.url).create_transaction()

    def commit(self):
        if not hasattr(self, 'tx_session'):
            raise SystemError("No transaction in progress, can't commit")

        results = self.tx_session.commit()
        delattr(self, 'tx_session')
        return results

    def rollback(self):
        if not hasattr(self, 'tx_session'):
            raise SystemError("No transaction in progress, can't rollback")

        self.tx_session.rollback()
        delattr(self, 'tx_session')

    def _execute_query(self, query, params):
        if hasattr(self, 'tx_session'):
            self.tx_session.append(query, params or {})
            results = self.tx_session.execute()[0]
            if results:
                return [list(results[0].values)], list(results[0].columns)
            else:
                return [], None
        else:
            if not hasattr(self, 'session'):
                self.new_session()
            cq = neo4j.CypherQuery(self.session, '')
            result = neo4j.CypherResults(cq._cypher._post({'query': query, 'params': params or {}}))
            return [list(r.values) for r in result.data], list(result.columns)

    def cypher_query(self, query, params=None, handle_unique=True):
        try:
            start = time.clock()
            results = self._execute_query(query, params)
            end = time.clock()
        except (ClientError, TransactionError) as e:
            if (handle_unique and e.message and " already exists with label " in e.message
                    and e.message.startswith('Node ')):
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
