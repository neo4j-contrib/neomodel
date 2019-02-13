from .core import StructuredNode, db
from .properties import AliasProperty
from .exceptions import MultipleNodesReturned
from .match_q import Q, QBase
import inspect
import re
OUTGOING, INCOMING, EITHER = 1, -1, 0


# basestring python 3.x fallback
try:
    basestring
except NameError:
    basestring = str


def _rel_helper(lhs, rhs, ident=None, relation_type=None, direction=None, relation_properties=None, **kwargs):
    """
    Generate a relationship matching string, with specified parameters.
    Examples:
    relation_direction = OUTGOING: (lhs)-[relation_ident:relation_type]->(rhs)
    relation_direction = INCOMING: (lhs)<-[relation_ident:relation_type]-(rhs)
    relation_direction = EITHER: (lhs)-[relation_ident:relation_type]-(rhs)

    :param lhs: The left hand statement.
    :type lhs: str
    :param rhs: The right hand statement.
    :type rhs: str
    :param ident: A specific identity to name the relationship, or None.
    :type ident: str
    :param relation_type: None for all direct rels, * for all of any length, or a name of an explicit rel.
    :type relation_type: str
    :param direction: None or EITHER for all OUTGOING,INCOMING,EITHER. Otherwise OUTGOING or INCOMING.
    :param relation_properties: dictionary of relationship properties to match
    :returns: string
    """

    if direction == OUTGOING:
        stmt = '-{0}->'
    elif direction == INCOMING:
        stmt = '<-{0}-'
    else:
        stmt = '-{0}-'

    rel_props = ''

    if relation_properties:
        rel_props = ' {{{0}}}'.format(', '.join(
            ['{0}: {1}'.format(key, value) for key, value in relation_properties.items()]))

    # direct, relation_type=None is unspecified, relation_type
    if relation_type is None:
        stmt = stmt.format('')
    # all("*" wildcard) relation_type
    elif relation_type == '*':
        stmt = stmt.format('[*]')
    else:
        # explicit relation_type
        stmt = stmt.format('[{0}:`{1}`{2}]'.format(ident if ident else '', relation_type, rel_props))

    return "({0}){1}({2})".format(lhs, stmt, rhs)


# special operators
_SPECIAL_OPERATOR_IN = 'IN'
_SPECIAL_OPERATOR_INSENSITIVE = '(?i)'
_SPECIAL_OPERATOR_ISNULL = 'IS NULL'
_SPECIAL_OPERATOR_ISNOTNULL = 'IS NOT NULL'
_SPECIAL_OPERATOR_REGEX = '=~'

_UNARY_OPERATORS = (_SPECIAL_OPERATOR_ISNULL, _SPECIAL_OPERATOR_ISNOTNULL)

_REGEX_INSESITIVE = _SPECIAL_OPERATOR_INSENSITIVE + '{}'
_REGEX_CONTAINS = '.*{}.*'
_REGEX_STARTSWITH = '{}.*'
_REGEX_ENDSWITH = '.*{}'

# regex operations that require escaping
_STRING_REGEX_OPERATOR_TABLE = {
    'iexact': _REGEX_INSESITIVE,
    'contains': _REGEX_CONTAINS,
    'icontains': _SPECIAL_OPERATOR_INSENSITIVE + _REGEX_CONTAINS,
    'startswith': _REGEX_STARTSWITH,
    'istartswith': _SPECIAL_OPERATOR_INSENSITIVE + _REGEX_STARTSWITH,
    'endswith': _REGEX_ENDSWITH,
    'iendswith': _SPECIAL_OPERATOR_INSENSITIVE + _REGEX_ENDSWITH,
}
# regex operations that do not require escaping
_REGEX_OPERATOR_TABLE = {
    'iregex': _REGEX_INSESITIVE,
}
# list all regex operations, these will require formatting of the value
_REGEX_OPERATOR_TABLE.update(_STRING_REGEX_OPERATOR_TABLE)

# list all supported operators
OPERATOR_TABLE = {
    'lt': '<',
    'gt': '>',
    'lte': '<=',
    'gte': '>=',
    'ne': '<>',
    'in': _SPECIAL_OPERATOR_IN,
    'isnull': _SPECIAL_OPERATOR_ISNULL,
    'regex': _SPECIAL_OPERATOR_REGEX,
    'exact': '='
}
# add all regex operators
OPERATOR_TABLE.update(_REGEX_OPERATOR_TABLE)


def install_traversals(cls, node_set):
    """
    For a StructuredNode class install Traversal objects for each
    relationship definition on a NodeSet instance
    """
    rels = cls.defined_properties(rels=True, aliases=False, properties=False)

    for key, value in rels.items():
        if hasattr(node_set, key):
            raise ValueError("Can't install traversal '{0}' exists on NodeSet".format(key))

        rel = getattr(cls, key)
        rel._lookup_node_class()

        traversal = Traversal(source=node_set, name=key, definition=rel.definition)
        setattr(node_set, key, traversal)


def process_filter_args(cls, kwargs):
    """
    loop through properties in filter parameters check they match class definition
    deflate them and convert into something easy to generate cypher from
    """

    output = {}

    for key, value in kwargs.items():
        if '__' in key:
            prop, operator = key.rsplit('__')
            operator = OPERATOR_TABLE[operator]
        else:
            prop = key
            operator = '='

        if prop not in cls.defined_properties(rels=False):
            raise ValueError("No such property {0} on {1}".format(prop, cls.__name__))

        property_obj = getattr(cls, prop)
        if isinstance(property_obj, AliasProperty):
            prop = property_obj.aliased_to()
            deflated_value = getattr(cls, prop).deflate(value)
        else:
            # handle special operators
            if operator == _SPECIAL_OPERATOR_IN:
                if not isinstance(value, tuple) and not isinstance(value, list):
                    raise ValueError('Value must be a tuple or list for IN operation {0}={1}'.format(key, value))
                deflated_value = [property_obj.deflate(v) for v in value]
            elif operator == _SPECIAL_OPERATOR_ISNULL:
                if not isinstance(value, bool):
                    raise ValueError('Value must be a bool for isnull operation on {0}'.format(key))
                operator = 'IS NULL' if value else 'IS NOT NULL'
                deflated_value = None
            elif operator in _REGEX_OPERATOR_TABLE.values():
                deflated_value = property_obj.deflate(value)
                if not isinstance(deflated_value, basestring):
                    raise ValueError('Must be a string value for {0}'.format(key))
                if operator in _STRING_REGEX_OPERATOR_TABLE.values():
                    deflated_value = re.escape(deflated_value)
                deflated_value = operator.format(deflated_value)
                operator = _SPECIAL_OPERATOR_REGEX
            else:
                deflated_value = property_obj.deflate(value)

        # map property to correct property name in the database
        db_property = cls.defined_properties(rels=False)[prop].db_property or prop

        output[db_property] = (operator, deflated_value)

    return output


def process_has_args(cls, kwargs):
    """
    loop through has parameters check they correspond to class rels defined
    """
    rel_definitions = cls.defined_properties(properties=False, rels=True, aliases=False)

    match, dont_match = {}, {}

    for key, value in kwargs.items():
        if key not in rel_definitions:
            raise ValueError("No such relation {0} defined on a {1}".format(key, cls.__name__))

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

            if hasattr(source, '_order_by'):
                self.build_order_by(ident, source)

            if source.filters or source.q_filters:
                self.build_where_stmt(ident, source.filters, source.q_filters, source_class=source.source_class)

            return ident
        elif isinstance(source, StructuredNode):
            return self.build_node(source)
        else:
            raise ValueError("Unknown source type " + repr(source))

    def create_ident(self):
        self._ident_count += 1
        return 'r' + str(self._ident_count)

    def build_order_by(self, ident, source):
        if '?' in source._order_by:
            self._ast['with'] = '{0}, rand() as r'.format(ident)
            self._ast['order_by'] = 'r'
        else:
            self._ast['order_by'] = ['{0}.{1}'.format(ident, p)
                                     for p in source._order_by]

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
        stmt = _rel_helper(lhs=lhs_ident, rhs=rhs_ident, ident=rel_ident, **traversal.definition)
        self._ast['match'].append(stmt)

        if traversal.filters:
            self.build_where_stmt(rel_ident, traversal.filters)

        return traversal.name

    def build_node(self, node):
        ident = node.__class__.__name__.lower()
        place_holder = self._register_place_holder(ident)

        # Hack to emulate START to lookup a node by id
        _node_lookup = 'MATCH ({0}) WHERE id({1})={{{2}}} WITH {3}'.format(ident, ident, place_holder, ident)
        self._ast['lookup'] = _node_lookup

        self._query_params[place_holder] = node.id

        self._ast['return'] = ident
        self._ast['result_class'] = node.__class__
        return ident

    def build_label(self, ident, cls):
        """
        match nodes by a label
        """
        ident_w_label = ident + ':' + cls.__label__
        self._ast['match'].append('({0})'.format(ident_w_label))
        self._ast['return'] = ident
        self._ast['result_class'] = cls
        return ident

    def build_additional_match(self, ident, node_set):
        """
            handle additional matches supplied by 'has()' calls
        """
        source_ident = ident

        for key, value in node_set.must_match.items():
            if isinstance(value, dict):
                label = ':' + value['node_class'].__label__
                stmt = _rel_helper(lhs=source_ident, rhs=label, ident='', **value)
                self._ast['where'].append(stmt)
            else:
                raise ValueError("Expecting dict got: " + repr(value))

        for key, val in node_set.dont_match.items():
            if isinstance(val, dict):
                label = ':' + val['node_class'].__label__
                stmt = _rel_helper(lhs=source_ident, rhs=label, ident='', **val)
                self._ast['where'].append('NOT ' + stmt)
            else:
                raise ValueError("Expecting dict got: " + repr(val))

    def _register_place_holder(self, key):
        if key in self._place_holder_registry:
            self._place_holder_registry[key] += 1
        else:
            self._place_holder_registry[key] = 1
        return key + '_' + str(self._place_holder_registry[key])

    def _parse_q_filters(self, ident, q, source_class):
        target = []
        for child in q.children:
            if isinstance(child, QBase):
                q_childs = self._parse_q_filters(ident, child, source_class)
                if child.connector == Q.OR:
                    q_childs = "(" + q_childs + ")"
                target.append(q_childs)
            else:
                kwargs = {child[0]: child[1]}
                filters = process_filter_args(source_class, kwargs)
                for prop, op_and_val in filters.items():
                    op, val = op_and_val
                    if op in _UNARY_OPERATORS:
                        # unary operators do not have a parameter
                        statement = '{0}.{1} {2}'.format(ident, prop, op)
                    else:
                        place_holder = self._register_place_holder(ident + '_' + prop)
                        statement = '{0}.{1} {2} {{{3}}}'.format(ident, prop, op, place_holder)
                        self._query_params[place_holder] = val
                    target.append(statement)
        ret = ' {0} '.format(q.connector).join(target)
        if q.negated:
            ret = 'NOT ({0})'.format(ret)
        return ret

    def build_where_stmt(self, ident, filters, q_filters=None, source_class=None):
        """
        construct a where statement from some filters
        """
        if q_filters is not None:
            stmts = self._parse_q_filters(ident, q_filters, source_class)
            if stmts:
                self._ast['where'].append(stmts)
        else:
            stmts = []
            for row in filters:
                negate = False

                # pre-process NOT cases as they are nested dicts
                if '__NOT__' in row and len(row) == 1:
                    negate = True
                    row = row['__NOT__']

                for prop, op_and_val in row.items():
                    op, val = op_and_val
                    if op in _UNARY_OPERATORS:
                        # unary operators do not have a parameter
                        statement = '{0} {1}.{2} {3}'.format('NOT' if negate else '', ident, prop, op)
                    else:
                        place_holder = self._register_place_holder(ident + '_' + prop)
                        statement = '{0} {1}.{2} {3} {{{4}}}'.format('NOT' if negate else '', ident, prop, op, place_holder)
                        self._query_params[place_holder] = val
                    stmts.append(statement)

            self._ast['where'].append(' AND '.join(stmts))

    def build_query(self):
        query = ''

        if 'lookup' in self._ast:
            query += self._ast['lookup']

        query += ' MATCH '
        query += ', '.join(['({0})'.format(i) for i in self._ast['match']])

        if 'where' in self._ast and self._ast['where']:
            query += ' WHERE '
            query += ' AND '.join(self._ast['where'])

        if 'with' in self._ast and self._ast['with']:
            query += ' WITH '
            query += self._ast['with']

        query += ' RETURN ' + self._ast['return']

        if 'order_by' in self._ast and self._ast['order_by']:
            query += ' ORDER BY '
            query += ', '.join(self._ast['order_by'])

        if 'skip' in self._ast:
            query += ' SKIP {0:d}'.format(self._ast['skip'])

        if 'limit' in self._ast:
            query += ' LIMIT {0:d}'.format(self._ast['limit'])

        return query

    def _count(self):
        self._ast['return'] = 'count({0})'.format(self._ast['return'])
        # drop order_by, results in an invalid query
        self._ast.pop('order_by', None)
        query = self.build_query()
        results, _ = db.cypher_query(query, self._query_params)
        return int(results[0][0])

    def _contains(self, node_id):
        # inject id = into ast
        ident = self._ast['return']
        place_holder = self._register_place_holder(ident + '_contains')
        self._ast['where'].append('id({0}) = {{{1}}}'.format(ident, place_holder))
        self._query_params[place_holder] = node_id
        return self._count() >= 1

    def _execute(self, lazy=False):
        if lazy:
            # inject id = into ast
            self._ast['return'] = 'id({})'.format(self._ast['return'])
        query = self.build_query()
        results, _ = db.cypher_query(query, self._query_params, resolve_objects=False)
        # The following is not as elegant as it could be but had to be copied from the
        # version prior to cypher_query with the resolve_objects capability.
        # It seems that certain calls are only supposed to be focusing to the first
        # result item returned (?)
        if results:
            return [self.node_set.source_class.inflate(n[0]) for n in results]
        return []
        
        
class BaseSet(object):
    """
    Base class for all node sets.

    Contains common python magic methods, __len__, __contains__ etc
    """
    query_cls = QueryBuilder

    def all(self, lazy=False):
        """
        Return all nodes belonging to the set
        :param lazy: False by default, specify True to get nodes with id only without the parameters.
        :return: list of nodes
        :rtype: list
        """
        return self.query_cls(self).build_ast()._execute(lazy)

    def __iter__(self):
        return (i for i in self.query_cls(self).build_ast()._execute())

    def __len__(self):
        return self.query_cls(self).build_ast()._count()

    def __bool__(self):
        return self.query_cls(self).build_ast()._count() > 0

    def __nonzero__(self):
        return self.query_cls(self).build_ast()._count() > 0

    def __contains__(self, obj):
        if isinstance(obj, StructuredNode):
            if hasattr(obj, 'id'):
                return self.query_cls(self).build_ast()._contains(int(obj.id))
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

            return self.query_cls(self).build_ast()._execute()

        elif isinstance(key, int):
            self.skip = key
            self.limit = 1

            return self.query_cls(self).build_ast()._execute()[0]


class NodeSet(BaseSet):
    """
    A class representing as set of nodes matching common query parameters
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
        self.q_filters = Q()

        # used by has()
        self.must_match = {}
        self.dont_match = {}

    def _get(self, limit=None, lazy=False, **kwargs):
        self.filter(**kwargs)
        if limit:
            self.limit = limit
        return self.query_cls(self).build_ast()._execute(lazy)

    def get(self, lazy=False, **kwargs):
        """
        Retrieve one node from the set matching supplied parameters
        :param lazy: False by default, specify True to get nodes with id only without the parameters.
        :param kwargs: same syntax as `filter()`
        :return: node
        """
        result = self._get(limit=2, lazy=lazy, **kwargs)
        if len(result) > 1:
            raise MultipleNodesReturned(repr(kwargs))
        elif not result:
            raise self.source_class.DoesNotExist(repr(kwargs))
        else:
            return result[0]

    def get_or_none(self, **kwargs):
        """
        Retrieve a node from the set matching supplied parameters or return none

        :param kwargs: same syntax as `filter()`
        :return: node or none
        """
        try:
            return self.get(**kwargs)
        except self.source_class.DoesNotExist:
            pass

    def first(self, **kwargs):
        """
        Retrieve the first node from the set matching supplied parameters

        :param kwargs: same syntax as `filter()`
        :return: node
        """
        result = result = self._get(limit=1, **kwargs)
        if result:
            return result[0]
        else:
            raise self.source_class.DoesNotExist(repr(kwargs))

    def first_or_none(self, **kwargs):
        """
        Retrieve the first node from the set matching supplied parameters or return none

        :param kwargs: same syntax as `filter()`
        :return: node or none
        """
        try:
            return self.first(**kwargs)
        except self.source_class.DoesNotExist:
            pass

    def filter(self, *args, **kwargs):
        """
        Apply filters to the existing nodes in the set.

        :param kwargs: filter parameters

            Filters mimic Django's syntax with the double '__' to separate field and operators.

            e.g `.filter(salary__gt=20000)` results in `salary > 20000`.

            The following operators are available:

             * 'lt': less than
             * 'gt': greater than
             * 'lte': less than or equal to
             * 'gte': greater than or equal to
             * 'ne': not equal to
             * 'in': matches one of list (or tuple)
             * 'isnull': is null
             * 'regex': matches supplied regex (neo4j regex format)
             * 'exact': exactly match string (just '=')
             * 'iexact': case insensitive match string
             * 'contains': contains string
             * 'icontains': case insensitive contains
             * 'startswith': string starts with
             * 'istartswith': case insensitive string starts with
             * 'endswith': string ends with
             * 'iendswith': case insensitive string ends with

        :return: self
        """
        if args or kwargs:
            self.q_filters = Q(self.q_filters & Q(*args, **kwargs))
        return self

    def exclude(self, *args, **kwargs):
        """
        Exclude nodes from the NodeSet via filters.

        :param kwargs: filter parameters see syntax for the filter method
        :return: self
        """
        if args or kwargs:
            self.q_filters = Q(self.q_filters & ~Q(*args, **kwargs))
        return self

    def has(self, **kwargs):
        must_match, dont_match = process_has_args(self.source_class, kwargs)
        self.must_match.update(must_match)
        self.dont_match.update(dont_match)
        return self

    def order_by(self, *props):
        """
        Order by properties. Prepend with minus to do descending. Pass None to
        remove ordering.
        """
        should_remove = len(props) == 1 and props[0] is None
        if not hasattr(self, '_order_by') or should_remove:
            self._order_by = []
            if should_remove:
                return self
        if '?' in props:
            self._order_by.append('?')
        else:
            for prop in props:
                prop = prop.strip()
                if prop.startswith('-'):
                    prop = prop[1:]
                    desc = True
                else:
                    desc = False

                if prop not in self.source_class.defined_properties(rels=False):
                    raise ValueError("No such property {0} on {1}".format(
                        prop, self.source_class.__name__))

                property_obj = getattr(self.source_class, prop)
                if isinstance(property_obj, AliasProperty):
                    prop = property_obj.aliased_to()

                self._order_by.append(prop + (' DESC' if desc else ''))

        return self


class Traversal(BaseSet):
    """
    Models a traversal from a node to another.

    :param source: Starting of the traversal.
    :type source: A :class:`~neomodel.core.StructuredNode` subclass, an
                  instance of such, a :class:`~neomodel.match.NodeSet` instance
                  or a :class:`~neomodel.match.Traversal` instance.
    :param name: A name for the traversal.
    :type name: :class:`str`
    :param definition: A relationship definition that most certainly deserves
                       a documentation here.
    :type defintion: :class:`dict`
    """

    def __init__(self, source, name, definition):
        """
        Create a traversal

        """
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
            raise TypeError("Bad source for traversal: "
                            "{0}".format(type(source)))

        invalid_keys = (
                set(definition) - {'direction', 'model', 'node_class', 'relation_type'}
        )
        if invalid_keys:
            raise ValueError(
                'Unallowed keys in Traversal definition: {invalid_keys}'
                .format(invalid_keys=invalid_keys)
            )

        self.definition = definition
        self.target_class = definition['node_class']
        self.name = name
        self.filters = []

    def match(self, **kwargs):
        """
        Traverse relationships with properties matching the given parameters.

            e.g: `.match(price__lt=10)`

        :param kwargs: see `NodeSet.filter()` for syntax
        :return: self
        """
        if kwargs:
            if self.definition.get('model') is None:
                raise ValueError("match() with filter only available on relationships with a model")
            output = process_filter_args(self.definition['model'], kwargs)
            if output:
                self.filters.append(output)
        return self
