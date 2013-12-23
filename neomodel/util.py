import re
from py2neo import neo4j
from .exception import UniqueProperty

camel_to_upper = lambda x: "_".join(word.upper() for word in re.split(r"([A-Z][0-9a-z]*)", x)[1::2])
upper_to_camel = lambda x: "".join(word.title() for word in x.split("_"))

# the default value "true;format=pretty" causes the server to loose individual status codes in batch responses
neo4j._headers[None] = [("X-Stream", "true")]


class CustomBatch(neo4j.WriteBatch):
    def __init__(self, graph, index_name, node='(unsaved)'):
        super(CustomBatch, self).__init__(graph)
        self.index_name = index_name
        self.node = node

    def submit(self):
        responses = self._execute()
        batch_responses = [neo4j.BatchResponse(r) for r in responses.json]
        self._check_for_conflicts(responses, batch_responses, self._requests)

        try:
            return [r.hydrated for r in batch_responses]
        finally:
            responses.close()

    def _check_for_conflicts(self, responses, batch_responses, requests):
        for i, r in enumerate(batch_responses):
            if r.status_code == 409:
                responses.close()
                raise UniqueProperty(
                        requests[i].body['key'], requests[i].body['key'],
                        self.index_name, self.node)
