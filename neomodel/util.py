import logging
import os
import time
import warnings
import sys
from threading import local

from py2neo import authenticate, Graph, Resource
from py2neo.batch import CypherJob
from py2neo.cypher import CypherTransaction, CypherResource, RecordList
from py2neo.cypher.core import RecordProducer
from py2neo.packages.httpstream.packages.urimagic import URI
from py2neo.cypher.error import ClientError
from py2neo.packages.httpstream import SocketError
from py2neo.util import is_collection

from .exception import CypherException, UniqueProperty, TransactionError
if sys.version_info >= (3, 0):
    from urllib.parse import urlparse
else:
    from urlparse import urlparse  # noqa

logger = logging.getLogger(__name__)

path_to_id = lambda val: int(URI(val).path.segments[-1])


class PatchedTransaction(CypherTransaction):
    def __init__(self, uri):
        super(PatchedTransaction, self).__init__(uri)

    def _post(self, resource):
        self.__assert_unfinished()
        rs = resource.post({"statements": self.statements})
        headers = dict(rs.headers)
        location = None
        # when run in python 2 the keys in the header dictionary all start with lowercase letters
        # but when run in python 3 they start with uppercase letters (so check for both)
        if "location" in headers:
            location = headers["location"]
        elif "Location" in headers:
            location = headers["Location"]
        if location is not None:
            self._execute = Resource(location)
        j = rs.json
        rs.close()
        self._clear()
        if "commit" in j:
            self._commit = Resource(j["commit"])
        if "errors" in j and len(j['errors']):
            error = j["errors"][0]
            txid = int(j['commit'].split('/')[-2])
            trace = error.get('stackTrace', error.get('stacktrace', ''))
            raise TransactionError(error['message'], error['code'], trace, txid)
        out = []
        for result in j["results"]:
            producer = RecordProducer(result["columns"])
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
            obj_type = URI(data['self']).path.segments[-2]
            if obj_type == 'node':
                return Node(data)
            elif obj_type == 'relationship':
                return Rel(data)
        raise NotImplemented("Don't know how to inflate: " + repr(data))
    elif is_collection(data):
        return type(data)([_hydrated(datum) for datum in data])
    else:
        return data

Graph._hydrated = _hydrated
CypherResource._hydrated = _hydrated
CypherTransaction = PatchedTransaction


class Database(local):
    def __init__(self, _url):
        if hasattr(self, 'session'):
            raise SystemError('__init__ called too many times')

        u = urlparse(_url)
        if u.netloc.find('@') > -1:
            credentials, self.host = u.netloc.rsplit('@', 1)
            self.user, self.password, = credentials.split(':')
            self.url = ''.join([u.scheme, '://', self.host, u.path, u.query])
            authenticate(self.host, self.user, self.password)
        else:
            self.url = _url

    def new_session(self):
        try:
            self.session = Graph(self.url)
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

        # make sure thread local session is set
        if not hasattr(self, 'session'):
            self.new_session()

        self.tx_session = self.session.cypher.begin()

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
            results = self.tx_session.process()[0]
            if results:
                return results, list(results.columns)
            else:
                return [], None
        else:
            if not hasattr(self, 'session'):
                self.new_session()
            results = self.session.cypher.execute(query, params)
            return results, list(results.columns)

    def cypher_query(self, query, params=None, handle_unique=True):
        try:
            start = time.clock()
            results = self._execute_query(query, params)
            end = time.clock()
        except (ClientError, TransactionError) as e:
            if (handle_unique and e.message and " already exists with label " in e.message
                    and e.message.startswith('Node ')):
                raise UniqueProperty(e.message)

            if isinstance(e, ClientError):
                raise e

            if isinstance(e, TransactionError):
                raise CypherException(query, params, e.message, e.java_exception, e.java_trace)

            raise CypherException(query, params, e.message, e.exception, e.stack_trace)

        if os.environ.get('NEOMODEL_CYPHER_DEBUG', False):
            logger.debug("query: " + query + "\nparams: " + repr(params) + "\ntook: %.2gs\n" % (end - start))

        return results

    def cypher_stream_query(self, query, params=None):
        """
        Streams the provided query, and generates responses when iterated.

        :param query:  A CYPHER query.
        :type query: str
        :param params: optional, key value params to pass into the query.
        :type params: dict
        :rtype: generator
        """
        # make sure thread local session is set
        if not hasattr(self, 'session'):
            self.new_session()

        return self.session.cypher.stream(query, params)

    def cypher_batch_query(self, queries, handle_unique=True):
        """
        Batch the provided queries, and returns all responses.

        :param queries:  List of tuples, each with a (cypher query, params)
        :type queries: list of tuples
        :rtype: list of RecordList
        """
        tx_created = False
        tx = getattr(self, 'tx_session', None)
        # operation requires a transaction for batch processing
        if not tx:
            # make sure thread local session is set
            if not hasattr(self, 'session'):
                self.new_session()
            tx = self.session.cypher.begin()
            tx_created = True

        try:
            # process all queries
            for q, params in queries:
                tx.append(q, params)
            results = tx.process()

            # if tx was created internally, make sure to commit changes
            if tx_created:
                tx.commit()

            return results
        except (ClientError, TransactionError) as e:
            # if tx was created internally, make try to rollback changes
            if tx_created:
                try:
                    tx.rollback()
                except:
                    pass

            if (handle_unique and e.message and " already exists with label " in e.message
                    and e.message.startswith('Node ')):
                raise UniqueProperty(e.message)

            if isinstance(e, ClientError):
                raise e

            if isinstance(e, TransactionError):
                raise CypherException(queries, {}, e.message, e.java_exception, e.java_trace)

            raise CypherException(queries, {}, e.message, e.exception, e.stack_trace)

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
