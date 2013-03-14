from .relationship import RelationshipDefinition, OUTGOING, INCOMING


class Traversal(object):
    def __init__(self, start_node):
        self.start_node = start_node
        assert hasattr(self.start_node, '__node__')
        self.query = [{'start': self.start_node.__node__.id,
            'class': self.start_node.__class__, 'name': 'origin'}]

    def traverse(self, rel_manager):
        assert hasattr(self.start_node, rel_manager)

        if len(self.query) > 1:
            t = self._follow_map(self.query[-1]['target_map'], rel_manager)
        else:
            t = getattr(self.start_node, rel_manager).definition
            t['name'] = rel_manager
        self.query.append(t)
        return self

    def _follow_map(self, target_map, rel_manager):
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
        last = self.query[-1]
        idents = []
        if isinstance(last, (list,)):
            idents = [x['name'] for x in last]
        else:
            idents = [last['name']]
        self.query.append({'return': idents})
        return self.query


def rel_helper(from_ident, rel, to_ident, rel_ident=''):
    if rel['direction'] == OUTGOING:
        stmt = '-[{0}:{1}]->'
    elif rel['direction'] == INCOMING:
        stmt = '<-[{0}:{1}]-'
    else:
        stmt = '-[{0}:{1}]-'
    stmt = stmt.format(rel_ident, rel['relation_type'])
    return "  ({0}){1}({2})".format(from_ident, stmt, to_ident)


class Query(object):
    def __init__(self, ast):
        self.ast = ast
        self.position = 0
        self.query = ''
        self.ident_count = 0
        self.where = []

    def _ident(self):
        self.ident_count += 1
        return 'r' + str(self.ident_count)

    def _build(self):
        for entry in self.ast:
            self.query += self._render(entry) + "\n"
            self.position += 1

    def _render(self, entry):
        if 'start' in entry:
            return self._render_start(entry)
        elif 'target_map' in entry:
            return self._render_relation(entry)
        elif 'where' in entry:
            return self._render_where(entry)
        elif 'return' in entry:
            return self._render_return(entry)

    def _render_start(self, entry):
        return "START origin=node(%d)" % entry['start']

    def _render_return(self, entry):
        return "RETURN " + ', '.join(entry['return'])

    def _render_relation(self, entry):
        from_ident = self.ast[self.position - 1]['name']
        stmt = "MATCH\n" if 'start' in self.ast[self.position - 1] else ''
        stmt += rel_helper(from_ident, entry, entry['name'])
        stmt += ",\n" + self._render_category_type_check(entry)
        if 'target_map' in self.ast[self.position + 1]:
            stmt += ','
        return stmt

    def _render_where(self, entry):
        expr = ' AND '.join(entry['where'])
        return "WHERE " + expr

    def _render_category_type_check(self, entry):
        ri = self._ident()
        rel_types = "|".join([rel for rel in entry['target_map']])
        desc = {'direction': INCOMING, 'relation_type': rel_types}
        self.ast[-1]['return'].append(ri)

        # Add where
        expr = ri + '.__instance__! = true'
        if 'where' in self.ast[-2]:
            self.ast[-2]['where'].append(expr)
        else:
            self.ast.insert(-1, {'where': [expr]})

        return rel_helper(entry['name'], desc, '', ri)

    def __str__(self):
        if not len(self.query):
            self._build()
        return self.query
