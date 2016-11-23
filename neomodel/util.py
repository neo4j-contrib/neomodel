import logging
import os
import time
import warnings
import sys
from threading import local

from .exception import UniqueProperty, ConstraintValidationFailed

from neo4j.v1 import GraphDatabase, basic_auth, exceptions as neo4j_exc


if sys.version_info >= (3, 0):
    from urllib.parse import urlparse
else:
    from urlparse import urlparse  # noqa


logger = logging.getLogger(__name__)


class Database(local):
    def __init__(self, _url):
        if hasattr(self, 'session'):
            raise SystemError('__init__ called too many times')

        u = urlparse(_url)
        if u.netloc.find('@') > -1:
            credentials, hostname = u.netloc.rsplit('@', 1)
            username, password, = credentials.split(':')
        else:
            raise ValueError("Expecting auth credentials in url, e.g: bolt://user:password@localhost")

        self.driver = GraphDatabase.driver('bolt://' + hostname,
                                           auth=basic_auth(username, password))
        self._active_transaction = None
        self.refresh_connection()

    def refresh_connection(self):
        if self._active_transaction:
            raise SystemError("Can't refresh connection with active transaction")

        self.session = self.driver.session()
        self._pid = os.getpid()
        self._active_transaction = None

    @property
    def transaction(self):
        return TransactionProxy(self)

    def begin(self):
        if self._active_transaction:
            raise SystemError("Transaction in progress")
        self._active_transaction = self.session.begin_transaction()

    def commit(self):
        r = self._active_transaction.commit()
        self._active_transaction = None
        return r

    def rollback(self):
        self._active_transaction.rollback()
        self._active_transaction = None

    def cypher_query(self, query, params=None, handle_unique=True):
        if self._pid != os.getpid():
            self.refresh_connection()

        if self._active_transaction:
            session = self._active_transaction
        else:
            session = self.session

        try:
            start = time.clock()
            response = session.run(query, params)
            results, meta = [list(r.values()) for r in response], response.keys()
            end = time.clock()
        except neo4j_exc.CypherError as ce:
            if ce.code == u'Neo.ClientError.Schema.ConstraintValidationFailed':
                if 'already exists with label' in ce.message and handle_unique:
                    raise UniqueProperty(ce.message)

                raise ConstraintValidationFailed(ce.message)
            else:
                exc_info = sys.exc_info()
                if sys.version_info >= (3, 0):
                    raise exc_info[1].with_traceback(exc_info[2])
                else:
                    raise exc_info[1]

        if os.environ.get('NEOMODEL_CYPHER_DEBUG', False):
            logger.debug("query: " + query + "\nparams: " + repr(params) + "\ntook: %.2gs\n" % (end - start))

        return results, meta


class TransactionProxy(object):

    def __init__(self, db):
        self.db = db

    def __enter__(self):
        self.db.begin()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_value:
            self.db.rollback()

        if exc_type is neo4j_exc.CypherError:
            if exc_value.code == u'Neo.ClientError.Schema.ConstraintValidationFailed':
                raise UniqueProperty(exc_value.message)

        if not exc_value:
            self.db.commit()

    def __call__(self, func):
        def wrapper(*args, **kwargs):
            with self:
                return func(*args, **kwargs)

        return wrapper


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
