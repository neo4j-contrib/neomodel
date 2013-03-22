from .relationship import RelationshipDefinition, OUTGOING, INCOMING


def last_name_in_ast(ast):
    for node in reversed(ast):
        if 'name' in node:
            return node['name']


def last_x_in_ast(ast, x):
    for node in reversed(ast):
        if x in node:
            return node
    raise Exception("Could not find {} in {}".format(x, ast))


class Traversal(object):
    def __init__(self, start_node):
        self.start_node = start_node
        self.ident_count = 0
        assert hasattr(self.start_node, '__node__')
        self.ast = [{'start': self.start_node.__node__.id,
            'class': self.start_node.__class__, 'name': 'origin'}]

    def traverse(self, rel_manager):
        assert hasattr(self.start_node, rel_manager)

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

    def _add_where(self, where):
        node = last_x_in_ast(self.ast, 'where')
        for rel in where['where']:
            node['where'].append(rel)

    def _create_ident(self):
        self.ident_count += 1
        return 'r' + str(self.ident_count)

    def _build_match_ast(self, target):
        rel_to_traverse = {
            'lhs': last_name_in_ast(self.ast),
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
            raise Exception("No such rel definition {0} on {1}".format(
                rel_manager, t_list))

        # return as list if more than one
        return targets if len(targets) > 1 else targets[0]

    def execute(self):
        node = last_x_in_ast(self.ast, 'name')
        idents = []
        if isinstance(node, (list,)):
            idents = [x['name'] for x in node]
        else:
            idents = [node['name']]
        if self.ident_count > 0:
            idents.append('type(r{})'.format(self.ident_count))
        self.ast.append({'return': idents})
        return self.ast


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
        self.position = 0
        self.query = ''
        self.ident_count = 0
        self.where = []

    def _create_ident(self):
        self.ident_count += 1
        return 'r' + str(self.ident_count)

    def _build(self):
        for entry in self.ast:
            self.query += self._render(entry) + "\n"
            self.position += 1

    def _render(self, entry):
        if 'start' in entry:
            return self._render_start(entry)
        elif 'match' in entry:
            return self._render_match(entry)
        elif 'where' in entry:
            return self._render_where(entry)
        elif 'return' in entry:
            return self._render_return(entry)

    def _render_start(self, entry):
        return "START origin=node(%d)" % entry['start']

    def _render_return(self, entry):
        return "RETURN " + ', '.join(entry['return'])

    def _render_match(self, entry):
        stmt = "MATCH\n" if 'start' in self.ast[self.position - 1] else ''
        stmt += ",\n".join([rel_helper(rel) for rel in entry['match']])
        return stmt

    def _render_where(self, entry):
        expr = ' AND '.join(entry['where'])
        return "WHERE " + expr

    def __str__(self):
        if not len(self.query):
            self._build()
        return self.query
