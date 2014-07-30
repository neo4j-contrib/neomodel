from .core import StructuredNode, db
from .properties import AliasProperty
from .exception import MultipleNodesReturned
import inspect
OUTGOING, INCOMING, EITHER = 1, -1, 0


def rel_helper(**rel):
    if rel['direction'] == OUTGOING:
        stmt = '-[{0}:{1}]->'
    elif rel['direction'] == INCOMING:
        stmt = '<-[{0}:{1}]-'
    else:
        stmt = '-[{0}:{1}]-'
    ident = rel['ident'] if 'ident' in rel else ''
    stmt = stmt.format(ident, rel['relation_type'])
    return "({0}){1}({2})".format(rel['lhs'], stmt, rel['rhs'])


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
    rels = cls.defined_properties(rels=True, aliases=False, properties=False)

    for key, value in rels.items():
        if hasattr(node_set, key):
            raise ValueError("Can't install traversal '{}' exists on NodeSet".format(key))

        rel = getattr(cls, key)
        rel._lookup_node_class()

        traversal = Traversal(source=node_set, key=key, definition=rel.definition)
        setattr(node_set, key, traversal)


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

        if prop not in cls.defined_properties(rels=False):
            raise ValueError("No such property {} on {}".format(prop, cls.__name__))

        property_obj = getattr(cls, prop)
        if isinstance(property_obj, AliasProperty):
            prop = property_obj.aliased_to()
            deflated_value = getattr(cls, prop).deflate(value)
        else:
            deflated_value = property_obj.deflate(value)

        output[prop] = (operator, deflated_value)

    return output


def process_has_args(cls, kwargs):
    """
    loop through has parameters check they correspond to class rels defined
    """
    rel_definitions = cls.defined_properties(properties=False, rels=True, aliases=False)

    match, dont_match = {}, {}

    for key, value in kwargs.items():
        if key not in rel_definitions:
            raise ValueError("No such relation {} defined on a {}".format(key, cls.__name__))

        rhs_ident = key

        rel_definitions[key]._lookup_node_class()

        if value is True:
            match[rhs_ident] = rel_definitions[key].definition
        elif value is False:
            dont_match[rhs_ident] = rel_definitions[key].definition
        elif isinstance(value, NodeSet):
            raise NotImplementedError("Not implemented yet")
        else:
            raise ValueError("Expecting True / False / NodeSet got: " + repr(value))

    return match, dont_match


class BaseSet(object):
    def all(self):
        return QueryBuilder(self).build_ast()._execute()

    def __iter__(self):
        return (i for i in QueryBuilder(self).build_ast()._execute())

    def __len__(self):
        return QueryBuilder(self).build_ast()._count()

    def __bool__(self):
        return QueryBuilder(self).build_ast()._count() > 0

    def __nonzero__(self):
        return QueryBuilder(self).build_ast()._count() > 0

    def __contains__(self, obj):
        if isinstance(obj, StructuredNode):
            if hasattr(obj, '_id'):
                return QueryBuilder(self).build_ast()._contains(int(obj._id))
            raise ValueError("Unsaved node: " + repr(obj))
        else:
            raise ValueError("Expecting StructuredNode instance")

    def __getitem__(self, key):
        if isinstance(key, slice):
            if key.stop and key.start:
                self.limit = key.stop - key.start
                self.skip = key.start
            elif key.stop:
                self.limit = key.stop
            elif key.start:
                self.skip = key.start
        elif isinstance(key, int):
            self.skip = key
            self.limit = 1

        return QueryBuilder(self).build_ast()._execute()


class NodeSet(BaseSet):
    """
    a set of matched nodes of a single type
        source: how to produce the set of nodes
        node_cls: what type of nodes are they
    """
    def __init__(self, source):
        self.source = source  # could be a Traverse object or a node class
        if isinstance(source, Traversal):
            self.source_class = source.target_class
        elif inspect.isclass(source) and issubclass(source, StructuredNode):
            self.source_class = source
        elif isinstance(source, StructuredNode):
            self.source_class = source.__class__
        else:
            raise ValueError("Bad source for nodeset " + repr(source))

        # setup Traversal objects using relationship definitions
        install_traversals(self.source_class, self)

        self.filters = []

        # used by has()
        self.must_match = {}
        self.dont_match = {}

    def get(self, **kwargs):
        output = process_filter_args(self.source_class, kwargs)
        self.filters.append(output)
        self.limit = 2
        result = QueryBuilder(self).build_ast()._execute()
        if len(result) > 1:
            raise MultipleNodesReturned(repr(kwargs))
        elif not result:
            raise self.source_class.DoesNotExist(repr(kwargs))
        else:
            return result[0]

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
        self.must_match.update(must_match)
        self.dont_match.update(dont_match)
        return self


class Traversal(BaseSet):
    """
        source: start of traversal could be any of: StructuredNode instance, StucturedNode class, NodeSet
        definition: relationship definition
    """
    def __init__(self, source, key, definition):
        self.source = source

        if isinstance(source, Traversal):
            self.source_class = source.target_class
        elif inspect.isclass(source) and issubclass(source, StructuredNode):
            self.source_class = source
        elif isinstance(source, StructuredNode):
            self.source_class = source.__class__
        elif isinstance(source, NodeSet):
            self.source_class = source.source_class
        else:
            raise ValueError("Bad source for traversal: {}".format(repr(source)))

        self.definition = definition
        self.target_class = definition['node_class']
        self.name = key
        self.filters = []

    def match(self, **kwargs):
        if 'model' not in self.definition:
            raise ValueError("match() only available on relationships with a model")
        if kwargs:
            self.filters.append(process_filter_args(self.definition['model'], kwargs))
        return self

    def _in_node_set(self):
        return NodeSet(self)


class QueryBuilder(object):
    def __init__(self, node_set):
        self.node_set = node_set
        self._ast = {'match': [], 'where': []}
        self._query_params = {}
        self._place_holder_registry = {}
        self._ident_count = 0

    def build_ast(self):
        self.build_source(self.node_set)

        if hasattr(self.node_set, 'skip'):
            self._ast['skip'] = self.node_set.skip
        if hasattr(self.node_set, 'limit'):
            self._ast['limit'] = self.node_set.limit

        return self

    def build_source(self, source):
        if isinstance(source, Traversal):
            return self.build_traversal(source)
        elif isinstance(source, NodeSet):
            if inspect.isclass(source.source) and issubclass(source.source, StructuredNode):
                ident = self.build_label(source.source.__label__.lower(), source.source)
            else:
                ident = self.build_source(source.source)

            self.build_additional_match(ident, source)

            if source.filters:
                self.build_where_stmt(ident, source.filters)

            return ident
        elif isinstance(source, StructuredNode):
            return self.build_node(source)
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
        rhs_label = ':' + traversal.target_class.__label__

        # build source
        lhs_ident = self.build_source(traversal.source)
        rhs_ident = traversal.name + rhs_label
        self._ast['return'] = traversal.name
        self._ast['result_class'] = traversal.target_class

        rel_ident = self.create_ident()
        stmt = rel_helper(lhs=lhs_ident, rhs=rhs_ident, ident=rel_ident, **traversal.definition)
        self._ast['match'].append(stmt)

        if traversal.filters:
            self.build_where_stmt(rel_ident, traversal.filters)

        return traversal.name

    def build_node(self, node):
        ident = node.__class__.__name__.lower()
        if 'start' not in self._ast:
            self._ast['start'] = []

        place_holder = self._register_place_holder(ident)
        self._ast['start'].append('{} = node({{{}}})'.format(ident, place_holder))
        self._query_params[place_holder] = node._id

        self._ast['return'] = ident
        self._ast['result_class'] = node.__class__
        return ident

    def build_label(self, ident, cls):
        """
        match nodes by a label
        """
        ident_w_label = ident + ':' + cls.__label__
        self._ast['match'].append('({})'.format(ident_w_label))
        self._ast['return'] = ident
        self._ast['result_class'] = cls
        return ident

    def build_additional_match(self, ident, node_set):
        """
            handle additional matches supplied by 'has()' calls
        """
        # TODO add support for labels
        source_ident = ident

        for key, value in node_set.must_match.items():
            label = ':' + value['node_class'].__label__
            if isinstance(value, dict):
                stmt = rel_helper(lhs=source_ident, rhs=label, ident='', **value)
                self._ast['where'].append(stmt)
            elif isinstance(value, tuple):
                rel_manager, ns = value
                self.add_node_set(ns, key)

        for key, val in node_set.dont_match.items():
            label = ':' + val['node_class'].__label__
            if isinstance(val, dict):
                stmt = rel_helper(lhs=source_ident, rhs=label, ident='', **val)
                self._ast['where'].append('NOT ' + stmt)
            else:
                raise ValueError("WTF? " + repr(val))

    def _register_place_holder(self, key):
        if key in self._place_holder_registry:
            self._place_holder_registry[key] += 1
        else:
            self._place_holder_registry[key] = 1
        return key + '_' + str(self._place_holder_registry[key])

    def build_where_stmt(self, ident, filters):
        """
        construct a where statement from some filters
        """
        stmts = []
        for row in filters:
            negate = False

            # pre-process NOT cases as they are nested dicts
            if '__NOT__' in row and len(row) == 1:
                negate = True
                row = row['__NOT__']

            for prop, op_and_val in row.items():
                op, val = op_and_val
                place_holder = self._register_place_holder(ident + '_' + prop)
                statement = '{} {}.{} {} {{{}}}'.format(
                    'NOT' if negate else '', ident, prop, op, place_holder)
                stmts.append(statement)
                self._query_params[place_holder] = val

        self._ast['where'].append(' AND '.join(stmts))

    def build_query(self):
        query = ''

        if 'start' in self._ast:
            query += 'START '
            query += ', '.join(self._ast['start'])

        query += ' MATCH '
        query += ', '.join(self._ast['match'])

        if 'where' in self._ast and self._ast['where']:
            query += ' WHERE '
            query += ' AND '.join(self._ast['where'])

        query += ' RETURN ' + self._ast['return']

        if 'skip' in self._ast:
            query += ' SKIP {0:d}'.format(self._ast['skip'])

        if 'limit' in self._ast:
            query += ' LIMIT {0:d}'.format(self._ast['limit'])

        return query

    def _count(self):
        self._ast['return'] = 'count({})'.format(self._ast['return'])
        query = self.build_query()
        results, _ = db.cypher_query(query, self._query_params)
        return int(results[0][0])

    def _contains(self, node_id):
        # inject id = into ast
        ident = self._ast['return']
        place_holder = self._register_place_holder(ident + '_contains')
        self._ast['where'].append('id({}) = {{{}}}'.format(ident, place_holder))
        self._query_params[place_holder] = node_id
        return self._count() == 1

    def _execute(self):
        query = self.build_query()
        results, _ = db.cypher_query(query, self._query_params)
        if results:
            return [self._ast['result_class'].inflate(n[0]) for n in results]
        return []
