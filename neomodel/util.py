import re
from py2neo import neo4j
from .exception import UniqueProperty, DataInconsistencyError

camel_to_upper = lambda x: "_".join(word.upper() for word in re.split(r"([A-Z][0-9a-z]*)", x)[1::2])
upper_to_camel = lambda x: "".join(word.title() for word in x.split("_"))


class CustomBatch(neo4j.WriteBatch):

    def __init__(self, graph, index_name, node='(unsaved)'):
        super(CustomBatch, self).__init__(graph)
        self.index_name = index_name
        self.node = node

    # def submit(self):
    #     results = []
    #     requests = self._requests
    #     try:
    #         results = self._execute().json
    #         # pre create or fail support need to catch 200 response
    #         if self._graph_db.neo4j_version < (1, 9):
    #             self._check_for_conflicts(results, requests)
    #     except neo4j.BatchError as r:
    #         key = requests[r.id].body['key']
    #         value = requests[r.id].body['value']
    #         raise UniqueProperty(key, value, self.index_name, self.node)
    #     else:
    #         return [
    #             self._graph_db._resolve(response.body, response.status, id_=response.id)
    #             for response in results
    #         ]

    def _check_for_conflicts(self, results, requests):
        for i, r in enumerate(results):
            if r['status'] == 200:
                raise DataInconsistencyError(requests[i], self.index_name, self.node)


def _legacy_conflict_check(cls, node, props):
    for key, value in props.items():
        if key in cls._class_properties() and cls.get_property(key).unique_index:
                results = cls.index.__index__.get(key, value)
                if len(results):
                    if isinstance(node, (int,)):  # node ref
                        raise UniqueProperty(key, value, cls.index.name)
                    elif hasattr(node, '_id') and results[0]._id != node._id:
                        raise UniqueProperty(key, value, cls.index.name, node)
