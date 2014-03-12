from .core import StructuredNode
from .relationship_manager import rel_helper
import inspect


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
    rel_definitions = cls.defined_properties(properties=False, rels=True, aliases=False)

    match, dont_match = {}, {}

    for key, value in kwargs.items():
        if not key in rel_definitions:
            raise ValueError("No such relation {} defined on a {}".format(key, cls.__name__))
        if value is True:
            match[key] = rel_definitions[key].definition
        elif value is False:
            dont_match[key] = rel_definitions[key].definition
        elif isinstance(value, NodeSet):
            raise NotImplementedError("Not implemented yet")
            dont_match[key] = (rel_definitions[key].definition, value)
        else:
            raise ValueError("Expecting True / False / NodeSet got: " + repr(value))

    return match, dont_match


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

        # setup Traversal objects using relationship definitions
        install_traversals(self.source_class, self)

        self.filters = []

        # used by has()
        self.must_match = {}
        self.dont_match = {}

    def filter(self, **kwargs):
        output = process_filter_args(self.source_class, kwargs)
        self.filters.append(output)
        return self

    def exclude(self, **kwargs):
        output = process_filter_args(self.source_class, kwargs)
        self.filters.append({'__NOT__': output})
        return self

    def has(self, **kwargs):
        must_match, dont_match = process_has_args(self.source_class, kwargs)
        # TODO catch conflicts, ie has(foo=True).has(foo=False)
        self.must_match.update(must_match)
        self.dont_match.update(dont_match)
        return self


class Traversal(object):
    """
        source: start of traversal could be any of: StructuredNode instance, StucturedNode class, NodeSet
        definition: relationship definition
        target: StructuredNode class
    """
    def __init__(self, source, key, definition):
        self.source = source
        self.definition = definition
        self.target_class = definition['label_map'].values()[0]
        self.name = key
        self.filters = []

    def match(self, **kwargs):
        if not 'model' in self.definition:
            raise ValueError("match() only available on relationships with a model")
        self.filters.append(process_filter_args(self.definition['model'], kwargs))
        return self


class QueryBuilder(object):
    def __init__(self, node_set):
        self.node_set = node_set
        self._ast = {'match': [], 'where': []}
        self._query_params = {}
        self._place_holder_registry = {}
        self._ident_count = 0

    def build_ast(self):
        self.build_source(self.node_set)

    def build_source(self, source):
        if isinstance(source, Traversal):
            return self.build_traversal(source)
        elif isinstance(source, NodeSet):
            if inspect.isclass(source.source) and issubclass(source.source, StructuredNode):
                ident = self.build_label(source.source.__label__.lower(), source.source)
            else:
                ident = self.build_source(source.source)
            self.build_additional_match(ident, source)
            return ident
        else:
            raise ValueError("Unknown source type " + repr(source))

    def create_ident(self):
        self._ident_count += 1
        return 'r' + str(self._ident_count)

    def build_traversal(self, traversal):
        """
        traverse a relationship from a node to a set of nodes
        """
        # build source
        lhs_ident = self.build_source(traversal.source)
        rhs_ident = traversal.name
        rel_ident = self.create_ident()
        stmt = rel_helper(lhs=lhs_ident, rhs=rhs_ident, ident=rel_ident, **traversal.definition)
        self._ast['match'].append(stmt)

        for filter_group in traversal.filters:
            where_stmt = self.build_where_stmt(rel_ident, filter_group)
            self._ast['where'].append(where_stmt)

    def build_node(self, node):
        ident = node.__class__.__name__.lower()
        self._ast['start'].append(['{} = node({})'.format(ident, node._id)])
        return ident

    def build_filters(self, node_set):
        for filter_group in node_set.filters:
            if '__NOT__' in filter_group:
                where_stmt = self.build_where_stmt(node_set.name, filter_group['__NOT__'])
                where_stmt = 'NOT ({})'.format(where_stmt)
            else:
                where_stmt = self.build_where_stmt(node_set.name, filter_group)

            self._ast['where'].append(where_stmt)

    def build_label(self, ident, cls):
        """
        match nodes by a label
        """
        ident_w_label = ident + ':' + cls.__label__
        self._ast['match'].append('({})'.format(ident_w_label))
        return ident_w_label

    def build_additional_match(self, source_ident, node_set):
        """
            handle additional matches supplied by 'has()' calls
        """
        for key, value in node_set.must_match.items():
            if isinstance(value, dict):
                stmt = rel_helper(lhs=source_ident, rhs=key, ident='', **value)
                self._ast['match'].append(stmt)
            elif isinstance(value, tuple):
                rel_manager, ns = value
                self.add_node_set(ns, key)

        for key, value in node_set.dont_match.items():
            if isinstance(value, dict):
                stmt = rel_helper(lhs=source_ident, rhs=key, ident='', **value)
                self._ast['where'].append('NOT ' + stmt)
            else:
                raise ValueError("WTF? " + repr(value))

    def _register_place_holder(self, key):
        if key in self._place_holder_registry:
            self._place_holder_registry[key] += 1
        else:
            self._place_holder_registry[key] = 1
        return key + '_' + str(self._place_holder_registry[key])

    def build_where_stmt(self, ident, filters):
        """
        construct a where statement
        """
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
