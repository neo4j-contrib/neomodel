import logging
import os
import time
import warnings
import sys
from threading import local

from .exception import UniqueProperty, ConstraintValidationFailed
from . import config

from neo4j.v1 import GraphDatabase, basic_auth, CypherError


if sys.version_info >= (3, 0):
    from urllib.parse import urlparse
else:
    from urlparse import urlparse  # noqa


logger = logging.getLogger(__name__)


# make sure the connection url has been set prior to executing the wrapped function
def ensure_connection(func):
    def wrapper(self, *args, **kwargs):
        if not self.url:
            self.set_connection(config.DATABASE_URL)
        return func(self, *args, **kwargs)
    return wrapper


def change_neo4j_password(db, new_password):
    db.cypher_query("CALL dbms.changePassword({password})", {'password': new_password})


def clear_neo4j_database(db):
    db.cypher_query("MATCH (a) DETACH DELETE a")


class Database(local):
    def __init__(self):
        self._active_transaction = None
        self.url = None
        self.driver = None
        self._pid = None

    def set_connection(self, url):
        self.url = url
        u = urlparse(url)

        if u.netloc.find('@') > -1 and u.scheme == 'bolt':
            credentials, hostname = u.netloc.rsplit('@', 1)
            username, password, = credentials.split(':')
        else:
            raise ValueError("Expecting url format: bolt://user:password@localhost:7687"
                             " got {}".format(url))

        self.driver = GraphDatabase.driver('bolt://' + hostname,
                                           auth=basic_auth(username, password),
                                           encrypted=config.ENCRYPTED_CONNECTION,
                                           max_pool_size=config.MAX_POOL_SIZE)

        self.refresh_connection()

    @ensure_connection
    def refresh_connection(self):
        if self._active_transaction:
            raise SystemError("Can't refresh connection with active transaction")

        self._session = self.driver.session()
        self._pid = os.getpid()
        self._active_transaction = None

    @property
    @ensure_connection
    def transaction(self):
        return TransactionProxy(self)

    @ensure_connection
    def begin(self):
        if self._active_transaction:
            raise SystemError("Transaction in progress")
        self._active_transaction = self._session.begin_transaction()

    @ensure_connection
    def commit(self):
        r = self._active_transaction.commit()
        self._active_transaction = None
        return r

    @ensure_connection
    def rollback(self):
        self._active_transaction.rollback()
        self._active_transaction = None

    @ensure_connection
    def cypher_query(self, query, params=None, handle_unique=True):
        if self._pid != os.getpid():
            self.refresh_connection()

        if self._active_transaction:
            session = self._active_transaction
        else:
            session = self._session

        try:
            start = time.clock()
            response = session.run(query, params)
            results, meta = [list(r.values()) for r in response], response.keys()
            end = time.clock()
        except CypherError as ce:
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

        if exc_type is CypherError:
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
