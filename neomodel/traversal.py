from .relationship_manager import RelationshipDefinition, rel_helper
from .util import cypher_query
from copy import deepcopy
import inspect
import re


def _deflate_node_value(label_map, prop, value):
    """
    When searching a query we must deflate our properties before making a query
    This helper functions attempts to deflate the properties by their structured node definition
    """
    prop = prop.replace('!', '').replace('?', '')
    property_classes = set()
    # find properties on potential classes
    for node_cls in label_map.values():
        if hasattr(node_cls, prop):
            property_classes.add(getattr(node_cls, prop).__class__)

    # attempt to deflate
    if len(property_classes) == 1:
        return property_classes.pop()().deflate(value)
    elif len(property_classes) > 1:
        classes = ' or '.join([cls.__name__ for cls in property_classes])
        node_classes = ' or '.join([cls.__name__ for cls in label_map.values()])
        raise ValueError("Unsure how to deflate '" + value + "' conflicting definitions "
                + " for target node classes " + node_classes + ", property could be any of: "
                + classes + " in where()")
    else:
        node_classes = ', '.join([cls.__name__ for cls in label_map.values()])
        raise ValueError("No property '{}' on {} can't deflate '{}' for where()".format(
            prop, node_classes, value))


def last_x_in_ast(ast, x):
    assert isinstance(ast, (list,))
    for node in reversed(ast):
        if x in node:
            return node
    raise IndexError("Could not find {0} in {1}".format(x, ast))


def unique_placeholder(placeholder, query_params):
    i = 0
    new_placeholder = "{}_{}".format(placeholder, i)
    while new_placeholder in query_params:
        i += 1
        new_placeholder = "{}_{}".format(placeholder, i)
    return new_placeholder


def _node_labeled(ident, labels):
    if len(labels) > 1:
        return ['({})'.format(
            ' OR '.join(['({}:{})'.format(ident, label) for label in labels]))]
    else:
        return ['({}:{})'.format(ident, labels[0])]


class AstBuilder(object):
    """Constructs a structure to be converted into a cypher query"""

    def __init__(self, start_node_or_class):
        self.ident_count = 0
        self.query_params = {}

        # traverse from class
        if inspect.isclass(start_node_or_class):
            self.start_class = start_node_or_class
            self.ast = [{
                'name': 'origin',
                'match': [{'label': start_node_or_class.__label__, 'ident': 'origin'}],
            }]
        else:
            self.start_class = start_node_or_class.__class__
            self.start_node = start_node_or_class
            self.query_params['self'] = start_node_or_class._id

            self.ast = [{'start': '{self}', 'name': 'origin'}]

        self.ast[0]['class'] = self.start_class
        self.ast[0]['label_map'] = {self.start_class.__label__: self.start_class}

    def _traverse(self, rel_manager, where_stmts=None):
        if len(self.ast) > 1:
            t = self._find_map(self.ast[-2]['label_map'], rel_manager)
        else:
            if not hasattr(self.start_class, rel_manager):
                    raise AttributeError("{} class has no relationship definition '{}' to traverse.".format(
                        self.start_class.__name__, rel_manager))
            # TODO use build_manager from class.
            t = getattr(self.start_node, rel_manager).definition
            t['name'] = rel_manager

        if where_stmts and not 'model' in t:
                raise Exception("Conditions " + repr(where_stmts) + " to traverse "
                        + rel_manager + " not allowed as no model specified on " + rel_manager)
        match, where = self._build_match_ast(t, where_stmts)
        self._add_match(match)
        if where:
            self._add_where(where)
        return self

    def _add_match(self, match):
        if len(self.ast) > 1:
            node = last_x_in_ast(self.ast, 'match')
            for rel in match['match']:
                node['match'].append(rel)
            # replace name and target map
            node['name'] = match['name']
            node['label_map'] = match['label_map']
        else:
            self.ast.append(match)

    def _add_where(self, where):
        if len(self.ast) > 2:
            node = last_x_in_ast(self.ast, 'where')
            for stmt in where:
                node['where'].append(stmt)
        else:
            self.ast.append({'where': where})

    def _create_ident(self):
        # ident generator
        self.ident_count += 1
        return 'r' + str(self.ident_count)

    def _build_match_ast(self, target, where_stmts):
        rel_to_traverse = {
            'lhs': last_x_in_ast(self.ast, 'name')['name'],
            'lhs_labels': last_x_in_ast(self.ast, 'name')['label_map'].keys(),
            'direction': target['direction'],
            'relation_type': target['relation_type'],
            'ident': self._create_ident(),
            'rhs': target['name'],
            'rhs_labels': target['label_map'].keys()
        }

        match = {
            'match': [rel_to_traverse],
            'name': target['name'],
            'label_map': target['label_map']
        }

        where_clause = _node_labeled(rel_to_traverse['lhs'], rel_to_traverse['lhs_labels'])
        where_clause += _node_labeled(rel_to_traverse['rhs'], rel_to_traverse['rhs_labels'])

        if where_stmts:
            where_clause += self._where_rel(where_stmts, rel_to_traverse['ident'], target['model'])

        return match, where_clause

    def _find_map(self, label_map, rel_manager):
        """
        When making a traverse find which relationship manager to follow
        - this can be ambiguous on multi class relationships
        - need to support some way of clarifying this
        """
        targets = []

        # find matching rel definitions
        for rel, cls in label_map.items():
            if hasattr(cls, rel_manager):
                manager = getattr(cls, rel_manager)
                if isinstance(manager, (RelationshipDefinition)):
                    p = manager.definition
                    p['name'] = rel_manager
                    # add to possible targets
                    targets.append(p)

        if not targets:
            t_list = ', '.join([t_cls.__name__ for t_cls, _ in label_map.items()])
            raise AttributeError("No such rel manager {0} on {1}".format(
                rel_manager, t_list))

        # return as list if more than one
        return targets if len(targets) > 1 else targets[0]

    def _where_node(self, ident_prop, op, value):
        if re.search(r'[^\w\?\!\.]', ident_prop):
            raise Exception("Invalid characters in ident allowed: [. \w ! ?]")
        target = last_x_in_ast(self.ast, 'name')
        if not '.' in ident_prop:
            prop = ident_prop
            ident_prop = target['name'] + '.' + ident_prop
        else:
            prop = ident_prop.split('.')[1]
        value = _deflate_node_value(target['label_map'], prop, value)
        return self._where_expr(ident_prop, op, value)

    def _where_rel(self, statements, rel_ident, model):
        stmts = []
        for statement in statements:
            rel_prop = statement[0].replace('!', '').replace('?', '')
            prop = getattr(model, rel_prop)
            if not prop:
                raise AttributeError("RelationshipManager '{}' on {} doesn't have a property '{}' defined".format(
                    rel_ident, self.start_class.__name__, rel_prop))
            val = prop.__class__().deflate(statement[2])
            stmts.append(self._where_expr(rel_ident + "." + statement[0], statement[1], val))
        return stmts

    def _where_expr(self, ident_prop, op, value):
        if not op in ['>', '<', '=', '<>', '=~']:
            raise Exception("Operator not supported: " + op)
        placeholder = re.sub('[!?]', '', ident_prop.replace('.', '_'))
        placeholder = unique_placeholder(placeholder, self.query_params)
        self.query_params[placeholder] = value
        return " ".join([ident_prop, op, '{' + placeholder + '}'])

    def _add_return(self, ast):
        node = last_x_in_ast(ast, 'name')
        idents = [node['name']]
        idents.append('labels({})'.format(idents[0]))
        ast.append({'return': idents})
        if hasattr(self, '_skip'):
            ast.append({'skip': int(self._skip)})
        if hasattr(self, '_limit'):
            ast.append({'limit': int(self._limit)})

    def _add_return_rels(self, ast):
        node = last_x_in_ast(ast, 'name')
        idents = [node['match'][0]['ident']]
        ast.append({'return': idents})
        if hasattr(self, '_skip'):
            ast.append({'skip': int(self._skip)})
        if hasattr(self, '_limit'):
            ast.append({'limit': int(self._limit)})

    def _set_order(self, ident_prop, desc=False):
        if not '.' in ident_prop:
            ident_prop = last_x_in_ast(self.ast, 'name')['name'] + '.' + ident_prop
        rel_manager, prop = ident_prop.split('.')

        # just in case input isn't safe
        assert not (re.search(r'[^\w]', rel_manager) and re.search(r'[^\w]', prop))

        name = last_x_in_ast(self.ast, 'name')['name']
        if name != rel_manager:
            raise ValueError("Last traversal was {0} not {1}".format(name, rel_manager))
        # set order
        if not hasattr(self, 'order_part'):
            self.order_part = {'order': ident_prop, 'desc': desc}
        else:
            raise NotImplemented("Order already set")

    def _add_return_count(self, ast):
        if hasattr(self, '_skip') or hasattr(self, '_limit'):
            raise NotImplemented("Can't use skip or limit with count")
        node = last_x_in_ast(ast, 'name')
        ident = ['count(' + node['name'] + ')']
        node = last_x_in_ast(ast, 'name')
        ast.append({'return': ident})

    def execute(self, ast):
        if hasattr(self, 'order_part'):
            # find suitable place to insert order node
            for i, entry in enumerate(reversed(ast)):
                if not ('limit' in entry or 'skip' in entry):
                    ast.insert(len(ast) - i, self.order_part)
                    break
        results, meta = cypher_query(self.connection, Query(ast), self.query_params)
        self.last_ast = ast
        return results

    def execute_and_inflate_nodes(self, ast):
        label_map = last_x_in_ast(ast, 'label_map')['label_map']
        results = self.execute(ast)
        nodes = [row[0] for row in results]
        # TODO: if they have multiple labels this will break
        classes = [label_map[row[1][0]] for row in results]
        return [cls.inflate(node) for node, cls in zip(nodes, classes)]


class TraversalSet(AstBuilder):
    """API level methods"""
    def __init__(self, connection, start_node_or_class):
        self.connection = connection
        super(TraversalSet, self).__init__(start_node_or_class)

    def traverse(self, rel=None, *where_stmts):
        if not hasattr(self.start_node, '_id'):
            raise ValueError("Cannot traverse unsaved node")
        self._traverse(rel, where_stmts)
        return self

    def order_by(self, prop):
        self._set_order(prop, desc=False)
        return self

    def order_by_desc(self, prop):
        self._set_order(prop, desc=True)
        return self

    def where(self, ident, op, value):
        expr = self._where_node(ident, op, value)
        self._add_where([expr])
        return self

    def skip(self, count):
        if int(count) < 0:
            raise ValueError("Negative skip value not supported")
        self._skip = int(count)
        return self

    def limit(self, count):
        if int(count) < 0:
            raise ValueError("Negative limit value not supported")
        self._limit = int(count)
        return self

    def run(self):
        ast = deepcopy(self.ast)
        self._add_return(ast)
        return self.execute_and_inflate_nodes(ast)

    def __iter__(self):
        return iter(self.run())

    def __len__(self):
        ast = deepcopy(self.ast)
        self._add_return_count(ast)
        return self.execute(ast)[0][0]

    def __bool__(self):
        return bool(len(self))

    def __nonzero__(self):
        return bool(len(self))


class Query(object):
    def __init__(self, ast):
        self.ast = ast

    def _build(self):
        self.position = 0
        self.ident_count = 0
        self.query = ''
        for entry in self.ast:
            self.query += self._render(entry) + "\n"
            self.position += 1
        return self.query

    def _render(self, entry):
        if 'start' in entry:
            return self._render_start(entry)
        elif 'match' in entry:
            return self._render_match(entry)
        elif 'where' in entry:
            return self._render_where(entry)
        elif 'return' in entry:
            return self._render_return(entry)
        elif 'skip' in entry:
            return self._render_skip(entry)
        elif 'limit' in entry:
            return self._render_limit(entry)
        elif 'order' in entry:
            return self._render_order(entry)

    def _render_start(self, entry):
        return "START origin=node(%s)" % entry['start']

    def _render_return(self, entry):
        return "RETURN " + ', '.join(entry['return'])

    def _render_match(self, entry):
        # add match clause if at start
        stmt = "MATCH\n" if (self.position - 1) < 1 else ''
        stmt += ",\n".join([
            # rel
            rel_helper(**e) if 'direction' in e
            # label
            else _node_labeled(e['ident'], [e['label']])[0]
            for e in entry['match']])
        return stmt

    def _render_where(self, entry):
        expr = ' AND '.join(entry['where'])
        return "WHERE " + expr

    def _render_skip(self, entry):
        return "SKIP {0}".format(entry['skip'])

    def _render_limit(self, entry):
        return "LIMIT {0}".format(entry['limit'])

    def _render_order(self, entry):
        sort = ' DESC' if entry['desc'] else ''
        return "ORDER BY {0}{1}".format(entry['order'], sort)

    def __str__(self):
        return self._build()
