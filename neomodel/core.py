import os
from .exception import DoesNotExist
from .properties import Property, PropertyManager
from .signals import hooks
from .util import Database, deprecated, classproperty


DATABASE_URL = os.environ.get('NEO4J_REST_URL', 'http://localhost:7474/db/data/')
db = Database(DATABASE_URL)


def install_labels(cls):
    # TODO when to execute this?
    for key, prop in cls.defined_properties(aliases=False, rels=False).items():
        if prop.index:
            db.cypher_query("CREATE INDEX on :{}({}); ".format(cls.__label__, key))
        elif prop.unique_index:
            db.cypher_query("CREATE CONSTRAINT on (n:{}) ASSERT n.{} IS UNIQUE; ".format(
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
                    raise ValueError("Class property called 'deleted' "
                            + "conflicts with neomodel internals")
                if issubclass(value.__class__, Property):
                    value.name = key
                    value.owner = inst
                    # support for 'magic' properties
                    if hasattr(value, 'setup') and hasattr(value.setup, '__call__'):
                        value.setup()
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

    @classproperty
    def nodes(cls):
        from .match import NodeSet
        return NodeSet(cls)

    def __init__(self, *args, **kwargs):
        if 'deleted' in kwargs:
            raise ValueError("deleted property is reserved for neomodel")

        for key, val in self.defined_properties(aliases=False, properties=False).items():
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
        return self.cypher("START self=node({self}) RETURN labels(self)")[0][0][0]

    def cypher(self, query, params=None):
        self._pre_action_check('cypher')
        params = params or {}
        params.update({'self': self._id})
        return db.cypher_query(query, params)

    @classmethod
    def inherited_labels(cls):
        return [scls.__label__ for scls in cls.mro()
                if hasattr(scls, '__label__') and not hasattr(scls, '__abstract_node__')]

    @classmethod
    @deprecated("Category nodes are now deprecated, the functionality is emulated using labels")
    def category(cls):
        return FakeCategory(cls)

    @hooks
    def save(self):
        # create or update instance node
        if hasattr(self, '_id'):
            # update
            query = "START self=node({self})\n"
            query += "\n".join(["SET self.{} = {{{}}}".format(key, key) + "\n"
                for key in self.__properties__.keys()])
            for label in self.inherited_labels():
                query += "SET self:`{}`\n".format(label)
            params = self.deflate(self.__properties__, self)
            self.cypher(query, params)
        elif hasattr(self, 'deleted') and self.deleted:
            raise ValueError("{}.save() attempted on deleted node".format(self.__class__.__name__))
        else: # create
            self._id = self.create(self.__properties__)[0]._id
        return self

    def _pre_action_check(self, action):
        if hasattr(self, 'deleted') and self.deleted:
            raise ValueError("{}.{}() attempted on deleted node".format(self.__class__.__name__, action))
        if not hasattr(self, '_id'):
            raise ValueError("{}.{}() attempted on unsaved node".format(self.__class__.__name__, action))

    @hooks
    def delete(self):
        self._pre_action_check('delete')
        self.cypher("START self=node({self}) OPTIONAL MATCH (self)-[r]-() DELETE r, self")
        del self.__dict__['_id']
        self.deleted = True
        return True

    def refresh(self):
        """Reload this object from its node id in the database"""
        self._pre_action_check('refresh')
        if hasattr(self, '_id'):
            node = self.inflate(self.cypher("START n=node({self}) RETURN n")[0][0][0])
            for key, val in node.__properties__.items():
                setattr(self, key, val)
        else:
            raise ValueError("Can't refresh unsaved node")

    @classmethod
    def create(cls, *props):
        query = ""
        deflated = [cls.deflate(p) for p in list(props)]
        params = {}
        for i in range(0, len(deflated)):
            props = ", ".join(["{}: {{n{}_{}}}".format(key, i, key)
                    for key, value in deflated[i].items()])
            query += "CREATE (n{} {{{}}})\n".format(i, props)

            for label in cls.inherited_labels():
                query += "SET n{}:`{}`\n".format(i, label)

            for key, value in deflated[i].items():
                params["n{}_{}".format(i, key)] = value

        query += "RETURN "
        query += ", ".join(["n" + str(i) for i in range(0, len(deflated))])

        results, meta = db.cypher_query(query, params)

        if hasattr(cls, 'post_create'):
            for node in results:
                node.post_create()

        return [cls.inflate(node) for node in results[0]]

    @classmethod
    def inflate(cls, node):
        props = {}
        for key, prop in cls.defined_properties(aliases=False, rels=False).items():
            if key in node._properties:
                props[key] = prop.inflate(node._properties[key], node)
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
        from .match import QueryBuilder
        return QueryBuilder(self._node_set)._count()

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
