import os
import re
import sys
import time
from functools import wraps
from _threading_local import local
from urllib.parse import urlparse

from neo4j.exceptions import CypherError
from neo4j.v1 import GraphDatabase, basic_auth, SessionError

from neomodel import config
from neomodel.exceptions import UniqueProperty, ConstraintValidationFailed
from neomodel.util import logger, registries


# database client


def ensure_connection(func):
    """
    This decorator ensures that the connection URL has been set prior to
    executing the wrapped function.
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.url:
            self.set_connection(config.DATABASE_URL)
        return func(self, *args, **kwargs)

    return wrapper


class Database(local):
    def __init__(self):
        self._active_transaction = None
        self.url = None
        self.driver = None
        self._pid = None

    def set_connection(self, url):
        u = urlparse(url)

        if u.netloc.find('@') > -1 and u.scheme in ('bolt', 'bolt+routing'):
            credentials, hostname = u.netloc.rsplit('@', 1)
            username, password, = credentials.split(':')
        else:
            raise ValueError(
                "Expecting url format: 'bolt://user:password@localhost:7687', "
                "got '{}'".format(url)
            )

        self.driver = GraphDatabase.driver(
            u.scheme + '://' + hostname,
            auth=basic_auth(username, password),
            encrypted=config.ENCRYPTED_CONNECTION,
            max_pool_size=config.MAX_POOL_SIZE
        )
        self.url = url
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
        self._active_transaction = self.driver.session().begin_transaction()

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
    def cypher_query(self, query, params=None, handle_unique=True,
                     retry_on_session_expire=False):
        if self._pid != os.getpid():
            self.set_connection(self.url)

        if self._active_transaction:
            session = self._active_transaction
        else:
            session = self.driver.session()

        try:
            start = time.clock()
            response = session.run(query, params)
            results = [list(r.values()) for r in response]
            meta = response.keys()
            end = time.clock()
        except CypherError as ce:
            if ce.code == u'Neo.ClientError.Schema.ConstraintValidationFailed':
                if 'already exists with label' in ce.message and handle_unique:
                    raise UniqueProperty(ce.message)

                raise ConstraintValidationFailed(ce.message)
            else:
                raise
        except SessionError:
            if retry_on_session_expire:
                self.set_connection(self.url)
                return self.cypher_query(
                    query=query, params=params, handle_unique=handle_unique,
                    retry_on_session_expire=False
                )
            raise

        if os.environ.get('NEOMODEL_CYPHER_DEBUG', False):
            logger.debug("query: " + query + "\nparams: " + repr(params)
                         + "\ntook: %.2gs\n" % (end - start))

        return results, meta


client = Database()


# context manager


class TransactionProxy:
    def __init__(self, db):
        self.db = db

    def __enter__(self):
        self.db.begin()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_value:
            self.db.rollback()

            if (exc_type is CypherError and
                exc_value.code == u'Neo.ClientError.Schema.ConstraintValidationFailed'):
                    raise UniqueProperty(exc_value.message)

        else:
            self.db.commit()

    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with self:
                return func(*args, **kwargs)

        return wrapper


# maintenance functions


def drop_constraints(quiet=True, stdout=None):
    """
    Discover and drop all constraints.

    :type: bool
    :return: None
    """

    results, meta = client.cypher_query("CALL db.constraints()")
    pattern = re.compile(':(.*) \).*\.(\w*)')
    for constraint in results:
        client.cypher_query('DROP ' + constraint[0])
        match = pattern.search(constraint[0])
        stdout.write(
            " - Dropping unique constraint and index on label {} with "
            "property {}.\n".format(match.group(1), match.group(2))
        )
    stdout.write("\n")


def change_neo4j_password(db, new_password):
    db.cypher_query("CALL dbms.changePassword({password})",
                    {'password': new_password})


def clear_neo4j_database(db):
    db.cypher_query("MATCH (a) DETACH DELETE a")


def drop_indexes(quiet=True, stdout=None):
    """
    Discover and drop all indexes.

    :type: bool
    :return: None
    """

    results, meta = client.cypher_query("CALL db.indexes()")
    pattern = re.compile(':(.*)\((.*)\)')
    for index in results:
        client.cypher_query('DROP ' + index[0])
        match = pattern.search(index[0])
        stdout.write(' - Dropping index on label {} with property {}.\n'
                     .format(match.group(1), match.group(2))
                     )
    stdout.write("\n")


def install_all_labels(stdout=None):
    """
    Execute :func:`install_labels` on each registered non-abstract node model.
    All model classes must have been imported to be registered.

    :param stdout: output stream
    """
    if not stdout:
        stdout = sys.stdout

    stdout.write("Setting up indexes and constraints...\n\n")

    for i, cls in enumerate(registries.concrete_node_models, start=1):
        stdout.write('Found {}.{}\n'.format(cls.__module__, cls.__name__))
        install_labels(cls, quiet=False, stdout=stdout)

    if i:
        stdout.write('\n')

    stdout.write('Finished {} classes.\n'.format(i))


def install_labels(cls, quiet=True, stdout=None):
    """
    Setup labels with indexes and constraints for a given class

    :param cls: StructuredNode class
    :type: class
    :param quiet: (default true) enable standard output
    :param stdout: stdout stream
    :type: bool
    :return: None
    """

    if not hasattr(cls, '__label__'):
        if not quiet:
            stdout.write(
                ' ! Skipping class {}.{} is abstract\n'
                .format(cls.__module__, cls.__name__)
            )
        return

    for name, property \
            in cls.defined_properties(aliases=False, rels=False).items():
        if property.index:
            if not quiet:
                stdout.write(
                    ' + Creating index {} on label {} for class {}.{}\n'
                    .format(name, cls.__label__, cls.__module__, cls.__name__)
                )

            client.cypher_query(
                "CREATE INDEX on :{label}({name});"
                .format(label=cls.__label__, name=name)
            )

        elif property.unique_index:
            if not quiet:
                stdout.write(
                    ' + Creating unique constraint for {} on label {} for '
                    'class {}.{}\n'.format(name, cls.__label__,
                                           cls.__module__, cls.__name__)
                )

            client.cypher_query(
                "CREATE CONSTRAINT on (n:{label}) ASSERT n.{name} IS UNIQUE;"
                .format(label=cls.__label__, name=name)
            )


def remove_all_labels(stdout=None):
    """
    Calls functions for dropping constraints and indexes.

    :param stdout: output stream
    :return: None
    """

    if not stdout:
        stdout = sys.stdout

    stdout.write("Droping constraints...\n")
    drop_constraints(quiet=False, stdout=stdout)

    stdout.write('Droping indexes...\n')
    drop_indexes(quiet=False, stdout=stdout)
