import re
from py2neo import neo4j
from .exception import UniqueProperty, DataInconsistencyError

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
        if self._graph_db.neo4j_version < (1, 9):
            self._legacy_check_for_conflicts(responses, batch_responses, self._requests)
        else:
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

    def _legacy_check_for_conflicts(self, responses, batch_responses, requests):
        for i, r in enumerate(batch_responses):
            if r.status_code == 200:
                responses.close()
                raise DataInconsistencyError(
                        requests[i].body['key'], requests[i].body['key'],
                        self.index_name, self.node)


def _legacy_conflict_check(cls, node, props):
    """
    prior to the introduction of create_or_fail in 1.9 we check to see if the key
    exists in the index before executing the batch.
    """
    for key, value in props.items():
        if key in cls._class_properties() and cls.get_property(key).unique_index:
            results = cls.index.__index__.get(key, value)
            if len(results):
                if isinstance(node, (int,)):  # node ref
                    raise UniqueProperty(key, value, cls.index.name)
                elif hasattr(node, '_id') and results[0]._id != node._id:
                    raise UniqueProperty(key, value, cls.index.name, node)
