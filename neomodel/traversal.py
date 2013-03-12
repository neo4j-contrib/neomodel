from .relationship import RelationshipDefinition, _related


class Traversal(object):
    def __init__(self, start_node):
        self.start_node = start_node
        assert hasattr(self.start_node, '__node__')
        self.query = [{'start': self.start_node.__node__.id,
            'class': self.start_node.__class__}]

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


class Query(object):
    def __init__(self, ast):
        self.ast = ast
        self.position = 0
        self.query = ''

    def _build(self):
        for entry in self.ast:
            self.query += self._render(entry) + "\n"
            self.position += 1

    def _render(self, entry):
        if 'start' in entry:
            return self._render_start(entry)
        elif 'target_map' in entry:
            return self._render_relation(entry)
        elif 'return' in entry:
            return self._render_return(entry)

    def _render_start(self, entry):
        return "START origin=node(%d)" % entry['start']

    def _render_return(self, entry):
        return "RETURN " + ', '.join(entry['return'])

    def _render_relation(self, entry):
        if self.position > 1:
            from_ident = self.ast[self.position - 1]['name']
        else:
            from_ident = 'origin'
        to_ident = entry['name']
        rel = _related(entry['direction']).format(entry['relation_type'])
        statement = "  ({0}){1}({2})".format(from_ident, rel, to_ident)
        if self.position == 1:
            return "MATCH\n" + statement
        return statement

    def __str__(self):
        self._build()
        return self.query
