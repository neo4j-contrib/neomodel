from .relationship import RelationshipDefinition, OUTGOING, INCOMING
from copy import deepcopy
import re


def last_x_in_ast(ast, x):
    assert isinstance(ast, (list,))
    for node in reversed(ast):
        if x in node:
            return node
    raise Exception("Could not find {0} in {1}".format(x, ast))


class AstBuilder(object):
    """Construct AST for traversal"""
    def __init__(self, start_node):
        self.start_node = start_node
        self.ident_count = 0
        assert hasattr(self.start_node, '__node__')
        self.ast = [{'start': '{self}',
            'class': self.start_node.__class__, 'name': 'origin'}]

    def _traverse(self, rel_manager):
        if len(self.ast) > 1:
            t = self._find_map(self.ast[-2]['target_map'], rel_manager)
        else:
            t = getattr(self.start_node, rel_manager).definition
            t['name'] = rel_manager

        match, where = self._build_match_ast(t)
        if len(self.ast) > 1:
            self._add_match(match)
            self._add_where(where)
        else:
            self.ast.append(match)
            self.ast.append(where)
        return self

    def _add_match(self, match):
        node = last_x_in_ast(self.ast, 'match')
        for rel in match['match']:
            node['match'].append(rel)
        # replace name and target map
        node['name'] = match['name']
        node['target_map'] = match['target_map']

    def _add_where(self, where):
        node = last_x_in_ast(self.ast, 'where')
        for rel in where['where']:
            node['where'].append(rel)

    def _create_ident(self):
        # ident generator
        self.ident_count += 1
        return 'r' + str(self.ident_count)

    def _build_match_ast(self, target):
        rel_to_traverse = {
            'lhs': last_x_in_ast(self.ast, 'name')['name'],
            'direction': target['direction'],
            'relation_type': target['relation_type'],
            'rhs': target['name'],
        }
        category_rel_ident = self._create_ident()
        rel_category_check = {
            'lhs': target['name'],
            'direction': INCOMING,
            'ident': category_rel_ident,
            'relation_type': "|".join([rel for rel in target['target_map']]),
            'rhs': ''
        }
        match = {
            'match': [rel_to_traverse, rel_category_check],
            'name': target['name'],
            'target_map': target['target_map']
        }

        # Add where
        expr = category_rel_ident + '.__instance__! = true'
        where = {'where': [expr]}
        return match, where

    def _find_map(self, target_map, rel_manager):
        targets = []
        # find matching rel definitions
        for rel, cls in target_map.iteritems():
            if hasattr(cls, rel_manager):
                manager = getattr(cls, rel_manager)
                if isinstance(manager, (RelationshipDefinition)):
                    p = manager.definition
                    p['name'] = rel_manager
                    # add to possible targets
                    targets.append(p)

        if not targets:
            t_list = ', '.join([t_cls.__name__ for t_cls in target_map.itervalues()])
            raise AttributeError("No such rel manager {0} on {1}".format(
                rel_manager, t_list))

        # return as list if more than one
        return targets if len(targets) > 1 else targets[0]

    def _add_return(self, ast):
        node = last_x_in_ast(ast, 'name')
        idents = [node['name']]
        if self.ident_count > 0:
            idents.append('r{0}'.format(self.ident_count))
        ast.append({'return': idents})

    def _add_skip_and_limit(self, ast, skip, limit):
        assert 'return' in ast[-1]
        if skip < 0 or limit < 0:
            raise IndexError("Negative indices not suppported")
        if skip:
            ast.append({'skip': skip})
        if limit:
            ast.append({'limit': limit})

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
        results, _ = self.start_node.cypher(Query(ast))
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

    def __iter__(self):
        ast = deepcopy(self.ast)
        self._add_return(ast)
        return iter(self.execute_and_inflate(ast))

    def __len__(self):
        ast = deepcopy(self.ast)
        self._add_return_count(ast)
        return self.execute(ast)[0][0]

    def __bool__(self):
        return bool(len(self))

    def __nonzero__(self):
        return bool(len(self))

    def __contains__(self, node):
        pass

    def __missing__(self, node):
        pass

    def __getitem__(self, index):
        ast = deepcopy(self.ast)
        self._add_return(ast)
        if isinstance(index, (slice,)):
            limit = index.stop - index.start
            self._add_skip_and_limit(ast, index.start, limit)
            return iter(self.execute_and_inflate(ast))
        elif isinstance(index, (int)):
            self._add_skip_and_limit(ast, index, 1)
            return self.execute_and_inflate(ast)[0]
        raise IndexError("Cannot index with " + index.__class__.__name__)


def rel_helper(rel):
    if rel['direction'] == OUTGOING:
        stmt = '-[{0}:{1}]->'
    elif rel['direction'] == INCOMING:
        stmt = '<-[{0}:{1}]-'
    else:
        stmt = '-[{0}:{1}]-'
    ident = rel['ident'] if 'ident' in rel else ''
    stmt = stmt.format(ident, rel['relation_type'])
    return "  ({0}){1}({2})".format(rel['lhs'], stmt, rel['rhs'])


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
        stmt += ",\n".join([rel_helper(rel) for rel in entry['match']])
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
