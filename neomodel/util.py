import logging
import os
import sys
import time
import warnings
from threading import local

from neo4j.v1 import GraphDatabase, basic_auth, CypherError, SessionError
from neo4j.types.graph import Node

from . import config
from .exceptions import UniqueProperty, ConstraintValidationFailed,  ModelDefinitionMismatch

if sys.version_info >= (3, 0):
    from urllib.parse import urlparse
else:
    from urlparse import urlparse  # noqa

logger = logging.getLogger(__name__)


# make sure the connection url has been set prior to executing the wrapped function
def ensure_connection(func):
    def wrapper(self, *args, **kwargs):
        # Sort out where to find url
        if hasattr(self, 'db'):
            _db = self.db
        else:
            _db = self

        if not _db.url:
            _db.set_connection(config.DATABASE_URL)
        return func(self, *args, **kwargs)

    return wrapper


def change_neo4j_password(db, new_password):
    db.cypher_query("CALL dbms.changePassword({password})", {'password': new_password})


def clear_neo4j_database(db):
    db.cypher_query("MATCH (a) DETACH DELETE a")


class NodeClassRegistry:
    """
    A singleton class via which all instances share the same Node Class Registry.
    """
    # Maintains a lookup directory that is used by cypher_query
    # to infer which class to instantiate by examining the labels of the
    # node in the resultset.
    # _NODE_CLASS_REGISTRY is populated automatically by the constructor
    # of the NodeMeta type.
    _NODE_CLASS_REGISTRY = {}

    def __init__(self):
        self.__dict__['_NODE_CLASS_REGISTRY'] = self._NODE_CLASS_REGISTRY

    def __str__(self):
        ncr_items = list(map(lambda x: "{} --> {}".format(",".join(x[0]), x[1]),
                         self._NODE_CLASS_REGISTRY.items()))
        return "\n".join(ncr_items)



class Database(local, NodeClassRegistry):
    """
    A singleton object via which all operations from neomodel to the Neo4j backend are handled with.
    """
    
    def __init__(self):
        """
        """
        self._active_transaction = None
        self.url = None
        self.driver = None
        self._pid = None

    def set_connection(self, url):
        """
        Sets the connection URL to the address a Neo4j server is set up at
        """
        u = urlparse(url)

        if u.netloc.find('@') > -1 and (u.scheme == 'bolt' or u.scheme == 'bolt+routing'):
            credentials, hostname = u.netloc.rsplit('@', 1)
            username, password, = credentials.split(':')
        else:
            raise ValueError("Expecting url format: bolt://user:password@localhost:7687"
                             " got {0}".format(url))

        self.driver = GraphDatabase.driver(u.scheme + '://' + hostname,
                                           auth=basic_auth(username, password),
                                           encrypted=config.ENCRYPTED_CONNECTION,
                                           max_pool_size=config.MAX_POOL_SIZE)
        self.url = url
        self._pid = os.getpid()
        self._active_transaction = None

    @property
    def transaction(self):
        """
        Returns the current transaction object
        """
        return TransactionProxy(self)

    @property
    def write_transaction(self):
        return TransactionProxy(self, access_mode="WRITE")
        
    @property
    def read_transaction(self):
        return TransactionProxy(self, access_mode="READ")        

    @ensure_connection
    def begin(self, access_mode=None):
        """
        Begins a new transaction, raises SystemError exception if a transaction is in progress
        """
        if self._active_transaction:
            raise SystemError("Transaction in progress")
        self._active_transaction = self.driver.session(access_mode=access_mode).begin_transaction()

    @ensure_connection
    def commit(self):
        """
        Commits the current transaction
        """
        r = self._active_transaction.commit()
        self._active_transaction = None
        return r

    @ensure_connection
    def rollback(self):
        """
        Rolls back the current transaction
        """
        self._active_transaction.rollback()
        self._active_transaction = None

    def _object_resolution(self, result_list):
        """
        Performs in place automatic object resolution on a set of results
        returned by cypher_query.

        The function operates recursively in order to be able to resolve Nodes
        within nested list structures. Not meant to be called directly,
        used primarily by cypher_query.
        
        :param result_list: A list of results as returned by cypher_query.
        :type list:
        
        :return: A list of instantiated objects.
        """
        
        # Object resolution occurs in-place
        for a_result_item in enumerate(result_list):
            for a_result_attribute in enumerate(a_result_item[1]):                    
                try:
                    # Primitive types should remain primitive types, 
                    #  Nodes to be resolved to native objects
                    resolved_object = a_result_attribute[1]
                    
                    if type(a_result_attribute[1]) is Node:
                        resolved_object = self._NODE_CLASS_REGISTRY[frozenset(a_result_attribute[1].labels)].inflate(
                            a_result_attribute[1])
                        
                    if type(a_result_attribute[1]) is list:
                        resolved_object = self._object_resolution([a_result_attribute[1]])                    
                    
                    result_list[a_result_item[0]][a_result_attribute[0]] = resolved_object
                    
                except KeyError:
                    # Not being able to match the label set of a node with a known object results 
                    # in a KeyError in the internal dictionary used for resolution. If it is impossible 
                    # to match, then raise an exception with more details about the error.
                    raise ModelDefinitionMismatch(a_result_attribute[1], self._NODE_CLASS_REGISTRY)
                    
        return result_list

        
        
    @ensure_connection
    def cypher_query(self, query, params=None, handle_unique=True, retry_on_session_expire=False, resolve_objects=False):
        """
        Runs a query on the database and returns a list of results and their headers.
        
        :param query: A CYPHER query
        :type: str
        :param params: Dictionary of parameters
        :type: dict
        :param handle_unique: Whether or not to raise UniqueProperty exception on Cypher's ConstraintValidation errors
        :type: bool
        :param retry_on_session_expire: Whether or not to attempt the same query again if the transaction has expired
        :type: bool        
        :param resolve_objects: Whether to attempt to resolve the returned nodes to data model objects automatically
        :type: bool
        """
        
        if self._pid != os.getpid():
            self.set_connection(self.url)

        if self._active_transaction:
            session = self._active_transaction
        else:
            session = self.driver.session()

        try:
            # Retrieve the data
            start = time.time()
            response = session.run(query, params)
            results, meta = [list(r.values()) for r in response], response.keys()
            end = time.time()
            
            if resolve_objects:
                # Do any automatic resolution required
                results = self._object_resolution(results)
                
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
        except SessionError:
            if retry_on_session_expire:
                self.set_connection(self.url)
                return self.cypher_query(query=query,
                                         params=params,
                                         handle_unique=handle_unique,
                                         retry_on_session_expire=False)
            raise

        if os.environ.get('NEOMODEL_CYPHER_DEBUG', False):
            logger.debug("query: " + query + "\nparams: " + repr(params) + "\ntook: {:.2g}s\n".format(end - start))

        return results, meta
        
        
class TransactionProxy(object):
    def __init__(self, db, access_mode=None):
        self.db = db
        self.access_mode = access_mode

    @ensure_connection
    def __enter__(self):
        self.db.begin(access_mode=self.access_mode)
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


# Just used for error messages
class _UnsavedNode(object):
    def __repr__(self):
        return '<unsaved node>'

    def __str__(self):
        return self.__repr__()


def _get_node_properties(node):
    """Get the properties from a neo4j.v1.types.graph.Node object."""
    # 1.6.x and newer have it as `_properties`
    if hasattr(node, '_properties'):
        return node._properties
    # 1.5.x and older have it as `properties`
    else:
        return node.properties
