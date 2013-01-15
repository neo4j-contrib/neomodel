import re
from py2neo import neo4j, rest
from .exception import UniqueProperty, DataInconsistencyError

camel_to_upper = lambda x: "_".join(word.upper() for word in re.split(r"([A-Z][0-9a-z]*)", x)[1::2])
upper_to_camel = lambda x: "".join(word.title() for word in x.split("_"))


class CustomBatch(neo4j.WriteBatch):

    def __init__(self, graph, index_name, node='(unsaved)'):
        super(CustomBatch, self).__init__(graph)
        self.index_name = index_name
        self.node = node

    def submit(self):
        results = []
        requests = self.requests
        try:
            results = self._submit()
            # pre create or fail support need to catch 200 response
            if self._graph_db.neo4j_version < (1, 8, 'M07'):
                self._check_for_conflicts(results, requests)
        except rest.ResourceConflict as r:
            key = requests[r.id].body['key']
            value = requests[r.id].body['value']
            raise UniqueProperty(key, value, self.index_name, self.node)
        else:
            return [
                self._graph_db._resolve(response.body, response.status, id_=response.id)
                for response in results
            ]

    def _check_for_conflicts(self, results, requests):
        i = 0
        for r in results:
            if r.status == 200:
                raise DataInconsistencyError(requests[i], self.index_name, self.node)
            i += 1
