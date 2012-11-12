from neomodel import (StructuredNode, StringProperty)


class PreSaveCalled(Exception):
    pass


class PreSaveHook(StructuredNode):
    name = StringProperty()

    def pre_save(self):
        raise PreSaveCalled


def test_pre_save():
    try:
        PreSaveHook(name='x').save()
    except PreSaveCalled:
        assert True
    else:
        assert False


class PostSaveCalled(Exception):
    pass


class PostSaveHook(StructuredNode):
    name = StringProperty()

    def post_save(self):
        raise PostSaveCalled


def test_post_save():
    try:
        PostSaveHook(name='x').save()
    except PostSaveCalled:
        assert True
    else:
        assert False


class PreDeleteCalled(Exception):
    pass


class PreDeleteHook(StructuredNode):
    name = StringProperty()

    def pre_delete(self):
        raise PreDeleteCalled


def test_pre_delete():
    try:
        PreDeleteHook(name='x').save().delete()
    except PreDeleteCalled:
        assert True
    else:
        assert False


class PostDeleteCalled(Exception):
    pass


class PostDeleteHook(StructuredNode):
    name = StringProperty()

    def post_delete(self):
        raise PostDeleteCalled


def test_post_delete():
    try:
        PostDeleteHook(name='x').save().delete()
    except PostDeleteCalled:
        assert True
    else:
        assert False
