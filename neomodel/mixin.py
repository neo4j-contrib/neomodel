class ReadOnlyNode(object):
    def delete():
        raise ReadOnlyError("You cannot delete read-only nodes")

    def update():
        raise ReadOnlyError("You cannot update read-only nodes")

    def save():
        raise ReadOnlyError("You cannot save read-only nodes")

    def __setattr__(self, key, value):
        if key.startswith('_'):
            self.__dict__[key] = value
            return
        raise ReadOnlyError("You cannot save properties on a read-only node")


class ReadOnlyError(Exception):
    pass
