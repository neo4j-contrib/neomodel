from neomodel import StructuredNode

OPERATOR_TABLE = {
    'lt': '<',
    'gt': '>',
    'lte': '<=',
    'gte': '>=',
    'ne': '<>',
}


def install_traversals(cls, node_set):
    """
    from a StructuredNode class install Traversal objects for each
    relationship definition on a NodeSet instance
    """
    pass


def process_filter_args(cls, kwargs):
    """
    loop through properties in filter parameters check they match class definition
    deflate them and convert into something easy to generate cypher from
    """

    output = {}

    for key, value in kwargs.items():
        if '__' in key:
            prop, operator = key.split('__')
            operator = OPERATOR_TABLE[operator]
        else:
            prop = key
            operator = '='

        if not prop in cls.defined_properties(rels=False, aliases=False):
            raise ValueError("No such property {} on {}".format(prop, cls.__name__))

        deflated_value = getattr(cls, prop).deflate(value)
        output[prop] = (operator, deflated_value)

    return output


def process_has_args(cls, kwargs):
    """
    loop through has parameters check they correspond to class rels defined
    """
    pass


class NodeSet(object):
    """
    a set of matched nodes of one type
        source: how to produce the set of nodes
        node_cls: what type of nodes are they
    """
    def __init__(self, source):
        self.source = source # could be a Traverse object or a node class
        if isinstance(source, Traversal):
            self.source_class = source.target_class
        elif issubclass(source, StructuredNode):
            self.source_class = source
        else:
            raise ValueError("Bad source for nodeset " + repr(source))

        self.name = self.source_class.__name__.lower()

        # setup Traversal objects using relationship definitions
        install_traversals(self.source_class, self)

        self.filters = []
        self.has_match = []

    def filter(self, **kwargs):
        output = process_filter_args(self.source_class, kwargs)
        self.filters.append(output)
        return self

    def exclude(self, **kwargs):
        output = process_filter_args(self.source_class, kwargs)
        self.filters.append({'__NOT__': output})
        return self

    def has(self, **kwargs):
        must_have = process_has_args(self.source_class, kwargs)
        self.has_match.append(must_have)
        return self

    def all(self):
        pass


class Traversal(object):
    """
        source: start of traversal could be any of: StructuredNode instance, StucturedNode class, NodeSet
        definition: relationship definition
        target: StructuredNode class
    """
    def __init__(self, source, definition, target):
        pass

    def match(self, **params):
        self.params = params
        return NodeSet(source=self)

    def all(self):
        return NodeSet(source=self)

    def filter(self, **params):
        return NodeSet(source=self).filter(**params)

    def exclude(self, **params):
        return NodeSet(source=self).exclude(**params)


class QueryBuilder(object):
    def __init__(self, node_set):
        self.node_set = node_set
        self._ast = {'match': [], 'where': []}
        self._query_params = {}
        self._place_holder_registry = {}

    def build_ast(self):
        if isinstance(self.node_set.source, Traversal):
            self.build_traversal(self.node_set)
        elif issubclass(self.node_set.source, StructuredNode):
            self.build_label(self.node_set)
        else:
            raise ValueError("Unknown source type")

        return self

    def build_label(self, node_set):
        self._ast['match'].append('({}:{})'.format(node_set.name, node_set.source.__label__))

        for filter_group in node_set.filters:
            if '__NOT__' in filter_group:
                where_stmt = self.build_where_stmt(node_set.name, filter_group['__NOT__'])
                where_stmt = 'NOT ({})'.format(where_stmt)
            else:
                where_stmt = self.build_where_stmt(node_set.name, filter_group)

            self._ast['where'].append(where_stmt)

    def _register_place_holder(self, key):
        if key in self._place_holder_registry:
            self._place_holder_registry[key] += 1
        else:
            self._place_holder_registry[key] = 1
        return key + '_' + str(self._place_holder_registry[key])

    def build_where_stmt(self, ident, filters):
        stmts = []
        for prop, op_and_val in filters.items():
            op, val = op_and_val
            place_holder = self._register_place_holder(ident + '_' + prop)
            stmts.append('{}.{} {} {{{}}}'.format(ident, prop, op, place_holder))
            self._query_params[place_holder] = val

        return ' AND '.join(stmts)

    def execute(self):
        self.build_ast()
        print repr(self._ast)
