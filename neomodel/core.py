import warnings

from .exception import DoesNotExist
from .properties import Property, PropertyManager
from .signals import hooks
from .util import Database, classproperty
from . import config

db = Database()


def install_labels(cls):
    for key, prop in cls.defined_properties(aliases=False, rels=False).items():
        if prop.index:
                db.cypher_query("CREATE INDEX on :{}({}); ".format(
                    cls.__label__, key))
        elif prop.unique_index:
                db.cypher_query("CREATE CONSTRAINT "
                                "on (n:{}) ASSERT n.{} IS UNIQUE; ".format(
                    cls.__label__, key))


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
            all_required = set(name for name, p in inst.defined_properties(aliases=False, rels=False).items()
                               if p.required or p.unique_index)
            inst.__required_properties__ = tuple(all_required)
            # cache all definitions
            inst.__all_properties__ = tuple(inst.defined_properties(aliases=False, rels=False).items())
            inst.__all_aliases__ = tuple(inst.defined_properties(properties=False, rels=False).items())
            inst.__all_relationships__ = tuple(inst.defined_properties(aliases=False, properties=False).items())

            if '__label__' in dct:
                inst.__label__ = dct['__label__']
            else:
                inst.__label__ = inst.__name__

            if config.AUTO_INSTALL_LABELS:
                install_labels(inst)

        return inst


NodeBase = NodeMeta('NodeBase', (PropertyManager,), {'__abstract_node__': True})


class StructuredNode(NodeBase):
    __abstract_node__ = True
    __required_properties__ = ()
    """ Names of all required properties of this StructuredNode """
    __all_properties__ = ()
    """ Tuple of (name, property) of all regular properties """
    __all_aliases__ = ()
    """ Tuple of (name, property) of all aliases """
    __all_relationships__ = ()
    """ Tuple of (name, property) of all relationships """

    @classproperty
    def nodes(cls):
        from .match import NodeSet

        return NodeSet(cls)

    @property
    def _id(self, val):
        warnings.warn('the _id property is deprecated please use .id',
                      category=DeprecationWarning, stacklevel=1)
        if val:
            self.id = val

        return self.id

    def __init__(self, *args, **kwargs):
        if 'deleted' in kwargs:
            raise ValueError("deleted property is reserved for neomodel")

        for key, val in self.__all_relationships__:
            self.__dict__[key] = val.build_manager(self, key)

        super(StructuredNode, self).__init__(*args, **kwargs)

    def __str__(self):
        return repr(self.__properties__)

    def __repr__(self):
        return '<{}: {}>'.format(self.__class__.__name__, self)

    def __eq__(self, other):
        if not isinstance(other, (StructuredNode,)):
            return False
        if hasattr(self, 'id') and hasattr(other, 'id'):
            return self.id == other.id
        return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def labels(self):
        self._pre_action_check('labels')
        return self.cypher("MATCH (n) WHERE id(n)={self} "
                           "RETURN labels(n)")[0][0][0]

    def cypher(self, query, params=None):
        self._pre_action_check('cypher')
        params = params or {}
        params.update({'self': self.id})
        return db.cypher_query(query, params)

    @classmethod
    def inherited_labels(cls):
        return [scls.__label__ for scls in cls.mro()
                if hasattr(scls, '__label__') and not hasattr(
                scls, '__abstract_node__')]

    @classmethod
    def category(cls):
        raise NotImplementedError("Category was deprecated and has now been removed, "
            "the functionality is now achieved using the {}.nodes attribute".format(cls.__name__))

    @hooks
    def save(self):
        # create or update instance node
        if hasattr(self, 'id'):
            # update
            params = self.deflate(self.__properties__, self)
            query = "MATCH (n) WHERE id(n)={self} \n"
            query += "\n".join(["SET n.{} = {{{}}}".format(key, key) + "\n"
                                for key in params.keys()])
            for label in self.inherited_labels():
                query += "SET n:`{}`\n".format(label)
            self.cypher(query, params)
        elif hasattr(self, 'deleted') and self.deleted:
            raise ValueError("{}.save() attempted on deleted node".format(
                self.__class__.__name__))
        else:  # create
            self.id = self.create(self.__properties__)[0].id
        return self

    def _pre_action_check(self, action):
        if hasattr(self, 'deleted') and self.deleted:
            raise ValueError("{}.{}() attempted on deleted node".format(
                self.__class__.__name__, action))
        if not hasattr(self, 'id'):
            raise ValueError("{}.{}() attempted on unsaved node".format(
                self.__class__.__name__, action))

    @hooks
    def delete(self):
        self._pre_action_check('delete')
        self.cypher("MATCH (self) WHERE id(self)={self} "
                    "OPTIONAL MATCH (self)-[r]-()"
                    " DELETE r, self")
        del self.__dict__['id']
        self.deleted = True
        return True

    def refresh(self):
        """Reload this object from its node id in the database"""
        self._pre_action_check('refresh')
        if hasattr(self, 'id'):
            node = self.inflate(self.cypher("MATCH (n) WHERE id(n)={self}"
                                            " RETURN n")[0][0][0])
            for key, val in node.__properties__.items():
                setattr(self, key, val)
        else:
            raise ValueError("Can't refresh unsaved node")

    @classmethod
    def _build_merge_query(cls, merge_params, update_existing=False, lazy=False, relationship=None):
        """
        Get a tuple of a CYPHER query and a params dict for the specified MERGE query.

        :param merge_params: The target node match parameters, each node must have a "create" key and optional "update".
        :type merge_params: list of dict
        :param update_existing: True to update properties of existing nodes, default False to keep existing values.
        :type update_existing: bool
        :rtype: tuple
        """
        query_params = dict(merge_params=merge_params)
        n_merge = "(n:{} {{{}}})".format(':'.join(cls.inherited_labels()),
                                         ", ".join("{0}: params.create.{0}".format(p) for p in cls.__required_properties__))
        if relationship is None:
            # create "simple" unwind query
            query = "UNWIND {{merge_params}} as params\n MERGE {}\n ".format(n_merge)
        else:
            # validate relationship
            if not isinstance(relationship.source, StructuredNode):
                raise ValueError("relationship source [%s] is not a StructuredNode" % repr(relationship.source))
            relation_type = relationship.definition.get('relation_type')
            if not relation_type:
                raise ValueError('No relation_type is specified on provided relationship')

            query_params["source_id"] = relationship.source.id
            query = "MATCH (source:{}) WHERE ID(source) = {{source_id}}\n ".format(relationship.source.__label__)
            query += "WITH source\n UNWIND {merge_params} as params \n "
            query += "MERGE (source)-[:{}]->{} \n ".format(relation_type, n_merge)

        query += "ON CREATE SET n = params.create\n "
        # if update_existing, write properties on match as well
        if update_existing is True:
            query += "ON MATCH SET n += params.update\n"

        # close query
        if lazy:
            query += "RETURN id(n)"
        else:
            query += "RETURN n"

        return query, query_params

    @classmethod
    def create(cls, *props, **kwargs):
        """
        Call to CREATE with parameters map. A new instance will be created and saved.

        :param props: List of dict arguments to get or create the entities with.
        :type props: tuple
        :param lazy: False by default, specify True to get nodes with id only without the parameters.
        :type lazy: bool
        :rtype: list
        """

        if 'streaming' in kwargs:
            warnings.warn('streaming is not supported by bolt, please remove the kwarg',
                          category=DeprecationWarning, stacklevel=1)

        lazy = kwargs.get('lazy', False)
        # create mapped query
        query = "CREATE (n:{} {{create_params}})".format(':'.join(cls.inherited_labels()))

        # close query
        if lazy:
            query += " RETURN id(n)"
        else:
            query += " RETURN n"

        results = []
        for item in [cls.deflate(p, skip_empty=True) for p in props]:
            node, _ = db.cypher_query(query, {'create_params': item})
            results.extend(node[0])

        nodes = [cls.inflate(node) for node in results]

        if not lazy and hasattr(cls, 'post_create'):
            for r in nodes[0]:
                r[0].post_create()

        return nodes

    @classmethod
    def get_or_create(cls, *props, **kwargs):
        """
        Call to MERGE with parameters map. A new instance will be created and saved if does not already exists,
        this is an atomic operation.
        Parameters must contain all required properties, any non required properties will be set on created nodes only.

        :param props: List of dict arguments to get or create the entities with.
        :type props: tuple
        :param relationship: Optional, relationship to get/create on when new entity is created.
        :param lazy: False by default, specify True to get nodes with id only without the parameters.
        :rtype: list
        """
        lazy = kwargs.get('lazy', False)
        relationship = kwargs.get('relationship')

        # build merge query
        get_or_create_params = [{"create": cls.deflate(p, skip_empty=True)} for p in props]
        query, params = cls._build_merge_query(get_or_create_params, relationship=relationship, lazy=lazy)

        if 'streaming' in kwargs:
            warnings.warn('streaming is not supported by bolt, please remove the kwarg',
                          category=DeprecationWarning, stacklevel=1)

        # fetch and build instance for each result
        results = db.cypher_query(query, params)
        # TODO: check each node if created call post_create()
        return [cls.inflate(r[0]) for r in results[0]]

    @classmethod
    def create_or_update(cls, *props, **kwargs):
        """
        Call to MERGE with parameters map. A new instance will be created and saved if does not already exists,
        this is an atomic operation. If an instance already exists all optional properties specified will be updated.

        :param props: List of dict arguments to get or create the entities with.
        :type props: tuple
        :param relationship: Optional, relationship to get/create on when new entity is created.
        :param lazy: False by default, specify True to get nodes with id only without the parameters.
        :rtype: list
        """
        lazy = kwargs.get('lazy', False)
        relationship = kwargs.get('relationship')

        # build merge query, make sure to update only explicitly specified properties
        create_or_update_params = []
        for specified, deflated in [(p, cls.deflate(p, skip_empty=True)) for p in props]:
            create_or_update_params.append({"create": deflated,
                                            "update": dict((k, v) for k, v in deflated.items() if k in specified)})
        query, params = cls._build_merge_query(create_or_update_params, update_existing=True, relationship=relationship,
                                               lazy=lazy)

        if 'streaming' in kwargs:
            warnings.warn('streaming is not supported by bolt, please remove the kwarg',
                          category=DeprecationWarning, stacklevel=1)

        # fetch and build instance for each result
        results = db.cypher_query(query, params)
        # TODO: check each node if created call post_create()
        return [cls.inflate(r[0]) for r in results[0]]

    @classmethod
    def inflate(cls, node):
        # support lazy loading
        if isinstance(node, int):
            snode = cls()
            snode.id = node
        else:
            props = {}
            for key, prop in cls.__all_properties__:
                # map property name from database to object property
                db_property = prop.db_property or key

                if db_property in node.properties:
                    props[key] = prop.inflate(node.properties[db_property], node)
                elif prop.has_default:
                    props[key] = prop.default_value()
                else:
                    props[key] = None

            snode = cls(**props)
            snode.id = node.id

        return snode
