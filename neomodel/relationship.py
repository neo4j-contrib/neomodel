from py2neo import neo4j

OUTGOING = neo4j.Direction.OUTGOING
INCOMING = neo4j.Direction.INCOMING
EITHER = neo4j.Direction.EITHER


class RelationshipManager(object):
    def __init__(self, direction, relation_type, name, node_class, origin):
        self.direction = direction
        self.relation_type = relation_type
        self.node_class = node_class
        self.name = name
        self.related = {}
        self.origin = origin

    @property
    def client(self):
        return self.origin._db.client

    def all(self):
        if not self.related:
            related_nodes = self.origin._node.get_related_nodes(self.direction, self.relation_type)
            if not related_nodes:
                return []

            props = self.client.get_properties(*related_nodes)
            for node, properties in dict(zip([n for n in related_nodes], props)).iteritems():
                wrapped_node = self.node_class(**(properties))
                wrapped_node._node = node
                self.related[node.id] = wrapped_node
            return [v for v in self.related.itervalues()]
        else:
            return [v for v in self.related.itervalues()]

    def is_related(self, obj):
        if obj._node.id in self.related:
            return True
        return self.origin._node.has_relationship_with(obj._node, self.direction, self.relation_type)

    def relate(self, obj):
        if obj.__class__ != self.node_class:
            raise Exception("Expecting object of class " + self.node_class.__name__)
        if not obj._node:
            raise Exception("Can't create relationship to unsaved node")

        self.client.get_or_create_relationships((self.origin._node, self.relation_type, obj._node),)
        self.related[obj._node.id] = obj

    def rerelate(self, old_obj, new_obj):
        if self.is_related(old_obj):
            if old_obj._node.id in self.related:
                del self.related[old_obj._node.id]
            rels = self.origin._node.get_relationships_with(
                    old_obj._node, self.direction, self.relation_type)
            for r in rels:
                r.delete()
        else:
            raise NotConnected(old_obj._node.id)

        self.client.get_or_create_relationships((self.origin._node, self.relation_type, new_obj._node),)
        self.related[new_obj._node.id] = new_obj

    def unrelate(self, obj):
        if obj._node.id in self.related:
            del self.related[obj._node.id]
        rels = self.origin._node.get_relationships_with(obj._node, self.direction, self.relation_type)
        if not rels:
            raise NotConnected(obj._node.id)
        if len(rels) > 1:
            raise Exception("Expected single relationship got {0}".format(rels))
        rels[0].delete()

    def single(self):
        nodes = self.all()
        if nodes:
            return nodes[0]
        else:
            return None


class RelationshipDefinition(object):
    def __init__(self, relation_type, cls, direction, manager=RelationshipManager):
        self.relation_type = relation_type
        self.node_class = cls
        self.manager = manager
        self.direction = direction

    def build_manager(self, origin, name):
        return self.manager(
                self.direction,
                self.relation_type,
                name,
                self.node_class,
                origin
               )


class RelationshipInstaller(object):
    """Replace relationship definitions with instances of RelationshipManager"""

    def __init__(self, *args, **kwargs):
        self._related = {}

        for key, value in self.__class__.__dict__.iteritems():
            if value.__class__ == RelationshipDefinition\
                    or issubclass(value.__class__, RelationshipDefinition):
                self._setup_relationship(key, value)

    def _setup_relationship(self, rel_name, rel_object):
        self.__dict__[rel_name] = rel_object.build_manager(self, rel_name)


class NotConnected(Exception):
    pass
