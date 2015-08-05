import os

from py2neo.cypher.error.schema import (IndexAlreadyExists,
                                        ConstraintAlreadyExists)

from .exception import DoesNotExist
from .properties import Property, PropertyManager
from .signals import hooks
from .util import Database, deprecated, classproperty

DATABASE_URL = os.environ.get('NEO4J_REST_URL', 'http://localhost:7474/db/data/')
db = Database(DATABASE_URL)


def install_labels(cls):
    # TODO when to execute this?
    if not hasattr(db, 'session'):
        db.new_session()
    for key, prop in cls.defined_properties(aliases=False, rels=False).items():
        if prop.index:
            indexes = db.session.schema.get_indexes(cls.__label__)
            if key not in indexes:
                try:
                    db.cypher_query("CREATE INDEX on :{}({}); ".format(
                        cls.__label__, key))
                except IndexAlreadyExists:
                    pass
        elif prop.unique_index:
            unique_const = db.session.schema.get_uniqueness_constraints(
                cls.__label__)
            if key not in unique_const:
                try:
                    db.cypher_query("CREATE CONSTRAINT "
                                    "on (n:{}) ASSERT n.{} IS UNIQUE; ".format(
                        cls.__label__, key))
                except (ConstraintAlreadyExists, IndexAlreadyExists):
                    pass


class NodeMeta(type):
    def __new__(mcs, name, bases, dct):
        dct.update({'DoesNotExist': type('DoesNotExist', (DoesNotExist,), dct)})
        inst = super(NodeMeta, mcs).__new__(mcs, name, bases, dct)

        if hasattr(inst, '__abstract_node__'):
            delattr(inst, '__abstract_node__')
        else:
            for key, value in dct.items():
                if key == 'deleted':
                    raise ValueError("Class property called 'deleted' conflicts with neomodel internals")

                if issubclass(value.__class__, Property):
                    value.name = key
                    value.owner = inst
                    # support for 'magic' properties
                    if hasattr(value, 'setup') and hasattr(
                            value.setup, '__call__'):
                        value.setup()

            # cache the names of all required and unique_index properties
            all_required = set(name for name, p in inst.defined_properties(aliases=False, rels=False).iteritems()
                               if p.required or p.unique_index)
            inst.__required_properties__ = tuple(all_required)

            if '__label__' in dct:
                inst.__label__ = dct['__label__']
            else:
                inst.__label__ = inst.__name__

            install_labels(inst)
            from .index import NodeIndexManager

            inst.index = NodeIndexManager(inst, inst.__label__)
        return inst


NodeBase = NodeMeta('NodeBase', (PropertyManager,), {'__abstract_node__': True})


class StructuredNode(NodeBase):
    __abstract_node__ = True
    __required_properties__ = ()

    @classproperty
    def nodes(cls):
        from .match import NodeSet

        return NodeSet(cls)

    def __init__(self, *args, **kwargs):
        if 'deleted' in kwargs:
            raise ValueError("deleted property is reserved for neomodel")

        for key, val in self.defined_properties(
                aliases=False, properties=False).items():
            self.__dict__[key] = val.build_manager(self, key)

        super(StructuredNode, self).__init__(*args, **kwargs)

    def __eq__(self, other):
        if not isinstance(other, (StructuredNode,)):
            return False
        if hasattr(self, '_id') and hasattr(other, '_id'):
            return self._id == other._id
        return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def labels(self):
        self._pre_action_check('labels')
        return self.cypher("MATCH n WHERE id(n)={self} "
                           "RETURN labels(n)")[0][0][0]

    def cypher(self, query, params=None):
        self._pre_action_check('cypher')
        params = params or {}
        params.update({'self': self._id})
        return db.cypher_query(query, params)

    @classmethod
    def inherited_labels(cls):
        return [scls.__label__ for scls in cls.mro()
                if hasattr(scls, '__label__') and not hasattr(
                scls, '__abstract_node__')]

    @classmethod
    @deprecated("Category nodes are now deprecated, the functionality is "
                "emulated using labels")
    def category(cls):
        return FakeCategory(cls)

    @hooks
    def save(self):
        # create or update instance node
        if hasattr(self, '_id'):
            # update
            query = "MATCH n WHERE id(n)={self} \n"
            query += "\n".join(["SET n.{} = {{{}}}".format(key, key) + "\n"
                                for key in self.__properties__.keys()])
            for label in self.inherited_labels():
                query += "SET n:`{}`\n".format(label)
            params = self.deflate(self.__properties__, self)
            self.cypher(query, params)
        elif hasattr(self, 'deleted') and self.deleted:
            raise ValueError("{}.save() attempted on deleted node".format(
                self.__class__.__name__))
        else:  # create
            self._id = self.create(self.__properties__)[0]._id
        return self

    def _pre_action_check(self, action):
        if hasattr(self, 'deleted') and self.deleted:
            raise ValueError("{}.{}() attempted on deleted node".format(
                self.__class__.__name__, action))
        if not hasattr(self, '_id'):
            raise ValueError("{}.{}() attempted on unsaved node".format(
                self.__class__.__name__, action))

    @hooks
    def delete(self):
        self._pre_action_check('delete')
        self.cypher("MATCH self WHERE id(self)={self} "
                    "OPTIONAL MATCH (self)-[r]-()"
                    " DELETE r, self")
        del self.__dict__['_id']
        self.deleted = True
        return True

    def refresh(self):
        """Reload this object from its node id in the database"""
        self._pre_action_check('refresh')
        if hasattr(self, '_id'):
            node = self.inflate(self.cypher("MATCH n WHERE id(n)={self}"
                                            " RETURN n")[0][0][0])
            for key, val in node.__properties__.items():
                setattr(self, key, val)
        else:
            raise ValueError("Can't refresh unsaved node")

    @classmethod
    def _validate_params(cls, params, required_only=False):
        """
        Validate property parameters for this class, split them into required and optional dicts. Raises any error if
        properties are missing, or if optional properties were provided with required_only=True.

        :param params:
        :type params: dict
        :param required_only: True to allow required properties only, otherwise False
        :type required_only: bool
        :return: A tuple of (required_params, optional_params)
        :rtype: tuple of dict, dict
        """
        required_params = dict((name, None) for name in cls.__required_properties__)
        optional_params = dict(params)

        # validate required params
        for required in required_params:
            value = params.get(required)
            if value is None:
                raise ValueError('Missing required property [%s] in %s' % (required, repr(params)))
            required_params[required] = value
            # remove required parameter
            optional_params.pop(required)

        # validate required params only
        if required_only and optional_params:
            raise ValueError('Required properties only expected, got optional: %s' % repr(optional_params))

        return required_params, optional_params

    @classmethod
    def _build_create_query(cls, create_params):
        """
        Get a tuple of a CYPHER query and a params dict for the specified CREATE query.

        :param create_params: The target node parameters.
        :type create_params: dict
        :rtype: tuple
        """
        props = ", ".join(["{0}: {{n_{0}}}".format(key) for key in create_params])
        params = dict(("n_{}".format(key), value) for key, value in create_params.iteritems())
        query = "CREATE (n {{{}}})\n".format(props)
        # add all inherited labels to the created entity
        for label in cls.inherited_labels():
            query += "SET n:`{}`\n".format(label)
        # close query
        query += "RETURN n"

        return query, params

    @classmethod
    def _build_merge_query(cls, match_params, update_params=None):
        """
        Get a tuple of a CYPHER query and a params dict for the specified MERGE query.

        :param match_params: The target node match parameters.
        :type match_params: dict
        :param update_params: The target node optional update parameters.
        :type update_params: dict
        :rtype: tuple
        """
        props = ", ".join(["{0}: {{n_{0}}}".format(key) for key in match_params])
        params = dict(("n_{}".format(key), value) for key, value in match_params.iteritems())
        query = "MERGE (n {{{}}})\n".format(props)
        # add update properties
        if update_params:
            update_props = ", ".join(["n.{0}={{n_{0}}}".format(key) for key in update_params])
            params.update(dict(("n_{}".format(key), value) for key, value in update_params.iteritems()))
            query += "ON CREATE SET {}\n".format(update_props)
            query += "ON MATCH SET {}\n".format(update_props)
        # add all inherited labels to the created entity
        for label in cls.inherited_labels():
            query += "SET n:`{}`\n".format(label)
        # close query
        query += "RETURN n"

        return query, params

    @classmethod
    def _build_create_unique_query(cls, source, relation_type, create_params):
        """
        Get a tuple of a CYPHER query and a params dict for the specified UNIQUE query.

        :param source: The source node.
        :type source: StructuredNode
        :param relation_type: The relationship type name.
        :type relation_type: str
        :param create_params: The target node parameters.
        :type create_params: dict
        :rtype: tuple
        """
        # build root match
        query = "MATCH (source:{}) WHERE ID(source) = {}\n".format(source.__label__, source._id)
        query += "CREATE UNIQUE (source)-[:{}]->(n:{} ".format(relation_type, cls.__label__)
        # add cls properties, and close create unique "})"
        props = ", ".join(["{0}: {{n_{0}}}".format(key) for key in create_params])
        params = dict(("n_{}".format(key), value) for key, value in create_params.iteritems())
        query += "{{{}}})\n".format(props)
        # add all inherited labels to the created entity
        for label in cls.inherited_labels():
            query += "SET n:`{}`\n".format(label)
        # close query
        query += "RETURN n"

        return query, params

    @classmethod
    def _stream_nodes(cls, results):
        """
        yeilds results

        :rtype: generator
        """
        post_create = hasattr(cls, 'post_create')

        for r in results:
            if post_create:
                r.one.post_create()
            yield cls.inflate(r.one)

    @classmethod
    def create(cls, *props, **kwargs):
        """
        Multiple calls to CREATE. A new instance will be created and saved.
        When using streaming=True, operation is not in current transaction if one exists.

        :param props: List of dict arguments to get or create the entities with.
        :type props: tuple
        :param streaming: Optional, Specify streaming=True to get a results generator instead of a list.
        :rtype: list
        """
        # build create queries
        queries = []
        # validate all properties have all required params, and only them
        for prop_params in [cls.deflate(p) for p in props]:
            # append each query after validating that all required parameters were specified
            cls._validate_params(prop_params)
            queries.append(cls._build_create_query(prop_params))

        if kwargs.get('streaming', False) is True:
            return cls._stream_nodes(db.cypher_stream_query(queries))
        else:
            # fetch and build instance for each result
            results = db.cypher_batch_query(queries)

            if hasattr(cls, 'post_create'):
                for node in results:
                    node.one.post_create()

            return [cls.inflate(r.one) for r in results]

    @classmethod
    def get_or_create(cls, *props, **kwargs):
        """
        Multiple calls to MERGE or CREATE UNIQUE when "relationship" is specified. A new instance will be created and
        saved if does not already exists, this is an atomic operation.
        Parameters must contain all required properties and only them, a ValueError is raised otherwise.
        When using streaming=True, operation is not in current transaction if one exists.

        :param props: List of dict arguments to get or create the entities with.
        :type props: tuple
        :param relationship: Optional, relationship to get/create on when new entity is created.
        :param streaming: Optional, Specify streaming=True to get a results generator instead of a list.
        :rtype: list
        """
        # get values for each properties dict in collection
        deflated = [cls.deflate(p) for p in props]
        # validate all properties have all required params, and only them
        for p in deflated:
            cls._validate_params(p, required_only=True)

        # define the build query type to use MERGE or CREATE UNIQUE and default args
        query_args = ()
        relationship = kwargs.get('relationship')
        if relationship is None:
            build_query_func = cls._build_merge_query
        else:
            # validate relationship
            if not isinstance(relationship.source, StructuredNode):
                raise ValueError("relationship source [%s] is not a StructuredNode" % repr(relationship.source))
            relation_type = relationship.definition.get('relation_type')
            if not relation_type:
                raise ValueError('No relation_type is specified on provided relationship')
            query_args = (relationship.source, relation_type)
            build_query_func = cls._build_create_unique_query

        # build all queries
        queries = [build_query_func(*(query_args + (p,))) for p in deflated]

        if kwargs.get('streaming', False) is True:
            return cls._stream_nodes(db.cypher_stream_query(queries))
        else:
            # fetch and build instance for each result
            results = db.cypher_batch_query(queries)
            # TODO: check each node if created call post_create()
            return [cls.inflate(r.one) for r in results]

    @classmethod
    def create_or_update(cls, *props, **kwargs):
        """
        Multiple calls to MERGE. A new instance will be created and saved if does not already exists, this is an atomic
        operation. If an instance already exists all optional properties specified will be updated.
        When using streaming=True, operation is not in current transaction if one exists.

        :param props: List of dict arguments to get or create the entities with.
        :type props: tuple
        :param streaming: Optional, Specify streaming=True to get a results generator instead of a list.
        :rtype: list
        """
        # build merge queries
        queries = []
        # validate all properties have all required params, and only them
        for prop_params in [cls.deflate(p) for p in props]:
            # append each query after validating and splitting into required and optional
            queries.append(cls._build_merge_query(*cls._validate_params(prop_params)))

        if kwargs.get('streaming', False) is True:
            return cls._stream_nodes(db.cypher_stream_query(queries))
        else:
            # fetch and build instance for each result
            results = db.cypher_batch_query(queries)
            # TODO: check each node if created call post_create()
            return [cls.inflate(r.one) for r in results]

    @classmethod
    def inflate(cls, node):
        props = {}
        for key, prop in cls.defined_properties(aliases=False, rels=False).items():
            if key in node.properties:
                props[key] = prop.inflate(node.properties[key], node)
            elif prop.has_default:
                props[key] = prop.default_value()
            else:
                props[key] = None

        snode = cls(**props)
        snode._id = node._id
        return snode


class FakeCategory(object):
    """
    Category nodes are no longer required with the introduction of labels.
    This class behaves like the old category nodes used in earlier version of neomodel
    but uses labels under the hood calling the traversal api.
    """

    def __init__(self, cls):
        self.instance = FakeInstanceRel(cls)

    def cypher(self, *args, **kwargs):
        raise NotImplemented("cypher method on category nodes no longer supported")


class FakeInstanceRel(object):
    """
    Fake rel manager for our fake category node
    """

    def __init__(self, cls):
        from .match import NodeSet

        self._node_set = NodeSet(cls)

    def __len__(self):
        return self._node_set.query_cls(self._node_set)._count()

    def __bool__(self):
        return len(self) > 0

    def __nonzero__(self):
        return len(self) > 0

    def count(self):
        return self.__len__()

    def all(self):
        return self._node_set.all()

    def search(self, **kwargs):
        ns = self._node_set
        for field, value in kwargs.items():
            ns.filter(**{field: value})
        return self._node_set.all()

    def get(self, **kwargs):
        result = self.search(**kwargs)
        if len(result) == 1:
            return result[0]
        if len(result) > 1:
            raise Exception("Multiple items returned, use search?")
        if not result:
            raise DoesNotExist("No items exist for the specified arguments")
