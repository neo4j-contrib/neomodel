import re
from py2neo import neo4j, rest
from .exception import UniqueProperty

camel_to_upper = lambda x: "_".join(word.upper() for word in re.split(r"([A-Z][0-9a-z]*)", x)[1::2])
upper_to_camel = lambda x: "".join(word.title() for word in x.split("_"))


class CustomBatch(neo4j.WriteBatch):

    def __init__(self, graph, index_name):
        super(CustomBatch, self).__init__(graph)
        self.index_name = index_name

    def submit(self):
        results = []
        requests = self.requests
        try:
            i = 0
            results = self._submit()
            # pre create or fail support need to catch 200 response
            for r in results:
                # TODO need to handle rollback??
                if r.status == 200:
                    raise UniqueProperty(requests[i], self.index_name)
                i += 1
        except rest.ResourceConflict as r:
            raise UniqueProperty(requests[r.id], self.index_name)
        else:
            return [
                self._graph_db._resolve(response.body, response.status, id_=response.id)
                for response in results
            ]
