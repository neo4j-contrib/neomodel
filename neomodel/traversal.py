from .relationship import RelationshipDefinition, OUTGOING, INCOMING
from copy import deepcopy


def last_x_in_ast(ast, x):
    for node in reversed(ast):
        if x in node:
            return node
    raise Exception("Could not find {} in {}".format(x, ast))


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

    def _finalise(self):
        node = last_x_in_ast(self.ast, 'name')
        idents = [node['name']]
        if self.ident_count > 0:
            idents.append('r{}'.format(self.ident_count))
        final_ast = deepcopy(self.ast)
        final_ast.append({'return': idents})
        return final_ast

    def _finalise_skip_limit(self, start, end):
        final_ast = self._finalise()
        if start < 0 or end < 0:
            raise NotImplemented("Negative indicies not suppported yet")
        if start:
            final_ast.append({'skip': start})
        if end:
            final_ast.append({'limit': end})
        return final_ast

    def _finalise_count(self):
        final_ast = deepcopy(self.ast)
        node = last_x_in_ast(final_ast, 'name')
        ident = ['count(' + node['name'] + ')']
        final_ast.append({'return': ident})
        return final_ast

    def _execute(self, ast):
        results, _ = self.start_node.cypher(Query(ast))
        return results

    def _execute_and_inflate(self, ast):
        target_map = last_x_in_ast(ast, 'target_map')['target_map']
        results = self._execute(ast)
        nodes = [row[0] for row in results]
        classes = [target_map[row[1].type] for row in results]
        return [cls.inflate(node) for node, cls in zip(nodes, classes)]


class TraversalSet(AstBuilder):
    """API level methods"""
    def __init__(self, start_node):
        super(TraversalSet, self).__init__(start_node)

    def traverse(self, rel):
        self._traverse(rel)
        return self

    def __iter__(self):
        ast = self._finalise()
        return iter(self._execute_and_inflate(ast))

    def __len__(self):
        ast = self._finalise_count()
        return self._execute(ast)[0][0]

    def __bool__(self):
        return bool(len(self))

    def __nonzero__(self):
        return bool(len(self))

    def __contains__(self, node):
        pass

    def __missing__(self, node):
        pass

    def __getitem__(self, index):
        if isinstance(index, (slice,)):
            ast = self._finalise_skip_limit(index.start, index.stop)
            return iter(self._execute_and_inflate(ast))
        elif isinstance(index, (int)):
            ast = self._finalise_skip_limit(index, 1)
            return self._execute_and_inflate(ast)
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

    def _render_start(self, entry):
        return "START origin=node(%s)" % entry['start']

    def _render_return(self, entry):
        return "RETURN " + ', '.join(entry['return'])

    def _render_match(self, entry):
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

    def __str__(self):
        return self._build()
