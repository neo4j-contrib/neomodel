class Traversal(object):
    def __init__(self, start_node):
        self.start_node = start_node
        assert hasattr(self.start_node, '__node__')
        self.query = [{'start': self.start_node.__node__.id,
            'class': self.start_node.__class__}]

    def traverse(self, rel_manager):
        assert hasattr(self.start_node, rel_manager)
        if len(self.query) > 2:
            pass
        else:
            t = getattr(self.start_node, rel_manager).definition
            t['name'] = rel_manager
        self.query.append(t)
        return self

    def execute(self):
        target = self.query[-1]['name']
        self.query.append({'return': target})
        return self.query
