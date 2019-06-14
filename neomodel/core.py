import re
import sys
import warnings

from neomodel import config
from neomodel.exceptions import DoesNotExist, ClassAlreadyDefined
from neomodel.hooks import hooks
from neomodel.properties import Property, PropertyManager
from neomodel.util import Database, classproperty, _UnsavedNode, _get_node_properties

db = Database()


def drop_constraints(quiet=True, stdout=None):
    """
    Discover and drop all constraints.

    :type: bool
    :return: None
    """

    results, meta = db.cypher_query("CALL db.constraints()")
    pattern = re.compile(':(.*) \).*\.(\w*)')
    for constraint in results:
        db.cypher_query('DROP ' + constraint[0])
        match = pattern.search(constraint[0])
        stdout.write(''' - Droping unique constraint and index on label {0} with property {1}.\n'''.format(
            match.group(1), match.group(2)))
    stdout.write("\n")


def drop_indexes(quiet=True, stdout=None):
    """
    Discover and drop all indexes.

    :type: bool
    :return: None
    """

    results, meta = db.cypher_query("CALL db.indexes()")
    pattern = re.compile(':(.*)\((.*)\)')
    for index in results:
        db.cypher_query('DROP ' + index[0])
        match = pattern.search(index[0])
        stdout.write(' - Dropping index on label {0} with property {1}.\n'.format(
            match.group(1), match.group(2)))
    stdout.write("\n")


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
            stdout.write(' ! Skipping class {0}.{1} is abstract\n'.format(cls.__module__, cls.__name__))
        return

    for name, property in cls.defined_properties(aliases=False, rels=False).items():
        db_property = property.db_property or name
        if property.index:
            if not quiet:
                stdout.write(' + Creating index {0} on label {1} for class {2}.{3}\n'.format(
                    name, cls.__label__, cls.__module__, cls.__name__))

            db.cypher_query("CREATE INDEX on :{0}({1}); ".format(
                cls.__label__, db_property))

        elif property.unique_index:
            if not quiet:
                stdout.write(' + Creating unique constraint for {0} on label {1} for class {2}.{3}\n'.format(
                    name, cls.__label__, cls.__module__, cls.__name__))

            db.cypher_query("CREATE CONSTRAINT "
                            "on (n:{0}) ASSERT n.{1} IS UNIQUE; ".format(
                cls.__label__, db_property))


def install_all_labels(stdout=None):
    """
    Discover all subclasses of StructuredNode in your application and execute install_labels on each.
    Note: code most be loaded (imported) in order for a class to be discovered.

    :param stdout: output stream
    :return: None
    """

    if not stdout:
        stdout = sys.stdout

    def subsub(cls):  # recursively return all subclasses
        return cls.__subclasses__() + [g for s in cls.__subclasses__() for g in subsub(s)]

    stdout.write("Setting up indexes and constraints...\n\n")

    i = 0
    for cls in subsub(StructuredNode):
        stdout.write('Found {0}.{1}\n'.format(cls.__module__, cls.__name__))
        install_labels(cls, quiet=False, stdout=stdout)
        i += 1

    if i:
        stdout.write('\n')

    stdout.write('Finished {0} classes.\n'.format(i))


class NodeMeta(type):
    def __new__(mcs, name, bases, namespace):
        namespace['DoesNotExist'] = \
            type(name + 'DoesNotExist', (DoesNotExist,), {})
        cls = super(NodeMeta, mcs).__new__(mcs, name, bases, namespace)
        # needed by Python < 3.5 for unpickling DoesNotExist objects:
        cls.DoesNotExist._model_class = cls

        if hasattr(cls, '__abstract_node__'):
            delattr(cls, '__abstract_node__')
        else:
            if 'deleted' in namespace:
                raise ValueError("Class property called 'deleted' conflicts "
                                 "with neomodel internals.")
            for key, value in ((x, y) for x, y in namespace.items()
                               if isinstance(y, Property)):
                value.name, value.owner = key, cls
                if hasattr(value, 'setup') and callable(value.setup):
                    value.setup()

            # cache various groups of properies
            cls.__required_properties__ = tuple(
                name for name, property
                in cls.defined_properties(aliases=False, rels=False).items()
                if property.required or property.unique_index
            )
            cls.__all_properties__ = tuple(
                cls.defined_properties(aliases=False, rels=False).items()
            )
            cls.__all_aliases__ = tuple(
                cls.defined_properties(properties=False, rels=False).items()
            )
            cls.__all_relationships__ = tuple(
                cls.defined_properties(aliases=False, properties=False).items()
            )

            cls.__label__ = namespace.get('__label__', name)

            if config.AUTO_INSTALL_LABELS:
                install_labels(cls)

            label_set = frozenset(cls.inherited_labels())
            if label_set not in db._NODE_CLASS_REGISTRY:
                db._NODE_CLASS_REGISTRY[label_set] = cls
            else:
                raise ClassAlreadyDefined(cls, db._NODE_CLASS_REGISTRY)

        return cls


NodeBase = NodeMeta('NodeBase', (PropertyManager,), {'__abstract_node__': True})


class StructuredNode(NodeBase):
    """
    Base class for all node definitions to inherit from.

    If you want to create your own abstract classes set:
        __abstract_node__ = True
    """

    # static properties

    __abstract_node__ = True

    # magic methods

    def __init__(self, *args, **kwargs):
        if 'deleted' in kwargs:
            raise ValueError("deleted property is reserved for neomodel")

        for key, val in self.__all_relationships__:
            self.__dict__[key] = val.build_manager(self, key)

        super(StructuredNode, self).__init__(*args, **kwargs)

    def __eq__(self, other):
        if not isinstance(other, (StructuredNode,)):
            return False
        if hasattr(self, 'id') and hasattr(other, 'id'):
            return self.id == other.id
        return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return '<{0}: {1}>'.format(self.__class__.__name__, self)

    def __str__(self):
        return repr(self.__properties__)

    # dynamic properties

    @classproperty
    def nodes(cls):
        """
        Returns a NodeSet object representing all nodes of the classes label
        :return: NodeSet
        :rtype: NodeSet
        """
        from .match import NodeSet
        return NodeSet(cls)

    @property
    def _id(self, val):
        warnings.warn('the _id property is deprecated please use .id',
                      category=DeprecationWarning, stacklevel=1)
        if val:
            self.id = val

        return self.id

    # methods

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
        n_merge = "n:{0} {{{1}}}".format(
            ":".join(cls.inherited_labels()),
            ", ".join("{0}: params.create.{0}".format(getattr(cls, p).db_property or p) for p in cls.__required_properties__))
        if relationship is None:
            # create "simple" unwind query
            query = "UNWIND {{merge_params}} as params\n MERGE ({0})\n ".format(n_merge)
        else:
            # validate relationship
            if not isinstance(relationship.source, StructuredNode):
                raise ValueError("relationship source [{0}] is not a StructuredNode".format(repr(relationship.source)))
            relation_type = relationship.definition.get('relation_type')
            if not relation_type:
                raise ValueError('No relation_type is specified on provided relationship')

            from .match import _rel_helper

            query_params["source_id"] = relationship.source.id
            query = "MATCH (source:{0}) WHERE ID(source) = {{source_id}}\n ".format(relationship.source.__label__)
            query += "WITH source\n UNWIND {merge_params} as params \n "
            query += "MERGE "
            query += _rel_helper(lhs='source', rhs=n_merge, ident=None,
                                 relation_type=relation_type, direction=relationship.definition['direction'])

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
    def category(cls):
        raise NotImplementedError("Category was deprecated and has now been removed, "
            "the functionality is now achieved using the {0}.nodes attribute".format(cls.__name__))

    @classmethod
    def create(cls, *props, **kwargs):
        """
        Call to CREATE with parameters map. A new instance will be created and saved.

        :param props: dict of properties to create the nodes.
        :type props: tuple
        :param lazy: False by default, specify True to get nodes with id only without the parameters.
        :type: bool
        :rtype: list
        """

        if 'streaming' in kwargs:
            warnings.warn('streaming is not supported by bolt, please remove the kwarg',
                          category=DeprecationWarning, stacklevel=1)

        lazy = kwargs.get('lazy', False)
        # create mapped query
        query = "CREATE (n:{0} {{create_params}})".format(':'.join(cls.inherited_labels()))

        # close query
        if lazy:
            query += " RETURN id(n)"
        else:
            query += " RETURN n"

        results = []
        for item in [cls.deflate(p, obj=_UnsavedNode(), skip_empty=True) for p in props]:
            node, _ = db.cypher_query(query, {'create_params': item})
            results.extend(node[0])

        nodes = [cls.inflate(node) for node in results]

        if not lazy and hasattr(cls, 'post_create'):
            for node in nodes:
                node.post_create()

        return nodes

    @classmethod
    def create_or_update(cls, *props, **kwargs):
        """
        Call to MERGE with parameters map. A new instance will be created and saved if does not already exists,
        this is an atomic operation. If an instance already exists all optional properties specified will be updated.

        Note that the post_create hook isn't called after create_or_update

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
        return [cls.inflate(r[0]) for r in results[0]]

    def cypher(self, query, params=None):
        """
        Execute a cypher query with the param 'self' pre-populated with the nodes neo4j id.

        :param query: cypher query string
        :type: string
        :param params: query parameters
        :type: dict
        :return: list containing query results
        :rtype: list
        """
        self._pre_action_check('cypher')
        params = params or {}
        params.update({'self': self.id})
        return db.cypher_query(query, params)

    @hooks
    def delete(self):
        """
        Delete a node and it's relationships

        :return: True
        """
        self._pre_action_check('delete')
        self.cypher("MATCH (self) WHERE id(self)={self} "
                    "OPTIONAL MATCH (self)-[r]-()"
                    " DELETE r, self")
        delattr(self, 'id')
        self.deleted = True
        return True

    @classmethod
    def get_or_create(cls, *props, **kwargs):
        """
        Call to MERGE with parameters map. A new instance will be created and saved if does not already exist,
        this is an atomic operation.
        Parameters must contain all required properties, any non required properties with defaults will be generated.

        Note that the post_create hook isn't called after get_or_create

        :param props: Arguments to get_or_create as tuple of dict with property names and values to get or create
                      the entities with.
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
        return [cls.inflate(r[0]) for r in results[0]]

    @classmethod
    def inflate(cls, node):
        """
        Inflate a raw neo4j_driver node to a neomodel node
        :param node:
        :return: node object
        """
        # support lazy loading
        if isinstance(node, int):
            snode = cls()
            snode.id = node
        else:
            node_properties = _get_node_properties(node)
            props = {}
            for key, prop in cls.__all_properties__:
                # map property name from database to object property
                db_property = prop.db_property or key

                if db_property in node_properties:
                    props[key] = prop.inflate(node_properties[db_property], node)
                elif prop.has_default:
                    props[key] = prop.default_value()
                else:
                    props[key] = None

            snode = cls(**props)
            snode.id = node.id

        return snode

    @classmethod
    def inherited_labels(cls):
        """
        Return list of labels from nodes class hierarchy.

        :return: list
        """
        return [scls.__label__ for scls in cls.mro()
                if hasattr(scls, '__label__') and not hasattr(
                scls, '__abstract_node__')]

    def labels(self):
        """
        Returns list of labels tied to the node from neo4j.

        :return: list of labels
        :rtype: list
        """
        self._pre_action_check('labels')
        return self.cypher("MATCH (n) WHERE id(n)={self} "
                           "RETURN labels(n)")[0][0][0]

    def _pre_action_check(self, action):
        if hasattr(self, 'deleted') and self.deleted:
            raise ValueError("{0}.{1}() attempted on deleted node".format(
                self.__class__.__name__, action))
        if not hasattr(self, 'id'):
            raise ValueError("{0}.{1}() attempted on unsaved node".format(
                self.__class__.__name__, action))

    def refresh(self):
        """
        Reload the node from neo4j
        """
        self._pre_action_check('refresh')
        if hasattr(self, 'id'):
            request = self.cypher("MATCH (n) WHERE id(n)={self}"
                                            " RETURN n")[0]
            if not request or not request[0]:
                raise self.__class__.DoesNotExist("Can't refresh non existent node")
            node = self.inflate(request[0][0])
            for key, val in node.__properties__.items():
                setattr(self, key, val)
        else:
            raise ValueError("Can't refresh unsaved node")

    @hooks
    def save(self):
        """
        Save the node to neo4j or raise an exception

        :return: the node instance
        """

        # create or update instance node
        if hasattr(self, 'id'):
            # update
            params = self.deflate(self.__properties__, self)
            query = "MATCH (n) WHERE id(n)={self} \n"
            query += "\n".join(["SET n.{0} = {{{1}}}".format(key, key) + "\n"
                                for key in params.keys()])
            for label in self.inherited_labels():
                query += "SET n:`{0}`\n".format(label)
            self.cypher(query, params)
        elif hasattr(self, 'deleted') and self.deleted:
            raise ValueError("{0}.save() attempted on deleted node".format(
                self.__class__.__name__))
        else:  # create
            self.id = self.create(self.__properties__)[0].id
        return self
