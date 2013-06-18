from .relationship import RelationshipDefinition, rel_helper, INCOMING
from .util import items
from copy import deepcopy
import re


def last_x_in_ast(ast, x):
    assert isinstance(ast, (list,))
    for node in reversed(ast):
        if x in node:
            return node
    raise IndexError("Could not find {0} in {1}".format(x, ast))


def unique_placeholder(placeholder, query_params):
        i = 0
        while placeholder in query_params:
            if placeholder + '_' + i in query_params:
                return placeholder + '_' + i
            i += 1
        return placeholder


class AstBuilder(object):
    """Construct AST for traversal"""
    def __init__(self, start_node):
        self.start_node = start_node
        self.ident_count = 0
        self.query_params = {}
        assert hasattr(self.start_node, '__node__')
        self.ast = [{'start': '{self}',
            'class': self.start_node.__class__, 'name': 'origin'}]
        self.origin_is_category = start_node.__class__.__name__ == 'CategoryNode'

    def _traverse(self, rel_manager):
        if len(self.ast) > 1:
            t = self._find_map(self.ast[-2]['target_map'], rel_manager)
        else:
            t = getattr(self.start_node, rel_manager).definition
            t['name'] = rel_manager

        match, where = self._build_match_ast(t)
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
            node['target_map'] = match['target_map']
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

    def _build_match_ast(self, target):
        rel_to_traverse = {
            'lhs': last_x_in_ast(self.ast, 'name')['name'],
            'direction': target['direction'],
            'relation_type': target['relation_type'],
            'ident': self._create_ident(),
            'rhs': target['name'],
        }

        match = {
            'match': [rel_to_traverse],
            'name': target['name'],
            'target_map': target['target_map']
        }

        # if we aren't category node or already traversed one rel
        if not self.origin_is_category or len(self.ast) > 1:
            category_rel_ident = self._create_ident()
            match['match'].append({
                'lhs': target['name'],
                'direction': INCOMING,
                'ident': category_rel_ident,
                'relation_type': "|".join([rel for rel in target['target_map']]),
                'rhs': ''
            })
            # Add where
            return match, [category_rel_ident + '.__instance__! = true']

        return match, []

    def _find_map(self, target_map, rel_manager):
        targets = []
        # find matching rel definitions
        for rel, cls in items(target_map):
            if hasattr(cls, rel_manager):
                manager = getattr(cls, rel_manager)
                if isinstance(manager, (RelationshipDefinition)):
                    p = manager.definition
                    p['name'] = rel_manager
                    # add to possible targets
                    targets.append(p)

        if not targets:
            t_list = ', '.join([t_cls.__name__ for t_cls, _ in items(target_map)])
            raise AttributeError("No such rel manager {0} on {1}".format(
                rel_manager, t_list))

        # return as list if more than one
        return targets if len(targets) > 1 else targets[0]

    def _add_filter(self, ident_prop, op, value):
        if re.search(r'[^\w\?\!\.]', ident_prop):
            raise Exception("Invalid characters in ident allowed: [. \w ! ?]")
        if not '.' in ident_prop:
            ident_prop = last_x_in_ast(self.ast, 'name')['name'] + '.' + ident_prop

        if not op in ['>', '<', '=', '<>', '=~']:
            raise Exception("Operator not supported: " + op)

        placeholder = re.sub('[!?]', '', ident_prop.replace('.', '_'))
        placeholder = unique_placeholder(placeholder, self.query_params)
        self.query_params[placeholder] = value
        self._add_where([" ".join([ident_prop, op, '{' + placeholder + '}'])])

    def _add_return(self, ast):
        node = last_x_in_ast(ast, 'name')
        idents = [node['name']]
        if self.ident_count > 0:
            idents.append('r{0}'.format(self.ident_count))
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
        results, _ = self.start_node.cypher(Query(ast), self.query_params)
        self.last_ast = ast
        return results

    def execute_and_inflate(self, ast):
        target_map = last_x_in_ast(ast, 'target_map')['target_map']
        results = self.execute(ast)
        nodes = [row[0] for row in results]
        classes = [target_map[row[1].type] for row in results]
        return [cls.inflate(node) for node, cls in zip(nodes, classes)]


class TraversalSet(AstBuilder):
    """API level methods"""
    def __init__(self, start_node):
        super(TraversalSet, self).__init__(start_node)

    def traverse(self, rel):
        if not self.start_node.__node__:
            raise Exception("Cannot traverse unsaved node")
        self._traverse(rel)
        return self

    def order_by(self, prop):
        self._set_order(prop, desc=False)
        return self

    def order_by_desc(self, prop):
        self._set_order(prop, desc=True)
        return self

    def where(self, ident, op, value):
        self._add_filter(ident, op, value)
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
        return self.execute_and_inflate(ast)

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

    def _create_ident(self):
        self.ident_count += 1
        return 'r' + str(self.ident_count)

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
        stmt = "MATCH\n" if 'start' in self.ast[self.position - 1] else ''
        stmt += ",\n".join([rel_helper(**rel) for rel in entry['match']])
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
