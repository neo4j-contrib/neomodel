from test._async_compat import mark_sync_test

from neomodel import RelationshipTo, StructuredNode


class SomeModel(StructuredNode):
    test = RelationshipTo("SomeModel", "SELF")


@mark_sync_test
def test_len_relationship():
    t1 = SomeModel().save()
    t2 = SomeModel().save()

    t1.test.connect(t2)
    l = len(t1.test.all())

    assert l
    assert l == 1
