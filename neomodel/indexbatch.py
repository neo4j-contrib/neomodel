from py2neo import neo4j, rest


class IndexBatch(object):

    def __init__(self, index):
        self.index = index
        self._uri = self.index._uri.reference
        self._graph_db = self.index._graph_db
        self._batch = neo4j.Batch(self._graph_db)

    @property
    def content_type(self):
        return self.index._content_type

    def add(self, key, value, entity):
        self._batch.append(rest.Request(self._graph_db, "POST", self._uri, {
            "key": key,
            "value": value,
            "uri": str(entity._uri),
        }))

    def add_if_none(self, key, value, entity):
        self._batch.append(rest.Request(self._graph_db, "POST", self._uri + "?unique", {
            "key": key,
            "value": value,
            "uri": str(entity._uri)
        }))

    def create_if_none(self, key, value, abstract):
        if self._content_type == neo4j.Node:
            body = {
                "key": key,
                "value": value,
                "properties": abstract
            }
        elif self._content_type == neo4j.Relationship:
            body = {
                "key": key,
                "value": value,
                "start": str(abstract[0]._uri),
                "type": abstract[1],
                "end": str(abstract[2]._uri),
                "properties": abstract[3] if len(abstract) > 3 else None
            }
        else:
            raise TypeError(self._content_type + " indexes are not supported")
        self._batch.append(
            rest.Request(self._graph_db, "POST", self._uri + "?unique", body)
        )

    def remove(self, key=None, value=None, entity=None):
        if key and value and entity:
            self._batch.append(rest.Request(
                self._graph_db, "DELETE", "{0}/{1}/{2}/{3}".format(
                    self._uri,
                    neo4j._quote(key, ""),
                    neo4j._quote(value, ""),
                    entity._id,
                )
            ))
        elif key and entity:
            self._batch.append(rest.Request(
                self._graph_db, "DELETE", "{0}/{1}/{2}".format(
                    self._uri,
                    neo4j._quote(key, ""),
                    entity._id,
                )
            ))
        elif entity:
            self._batch.append(rest.Request(
                self._graph_db, "DELETE", "{0}/{1}".format(
                    self._uri,
                    entity._id,
                )
            ))
        else:
            raise TypeError("Illegal parameter combination for index removal")

    def submit(self):
        return self._batch.submit()
