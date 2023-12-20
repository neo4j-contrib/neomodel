from neomodel import AsyncRelationshipTo, AsyncStructuredNode


class SomeModel(AsyncStructuredNode):
    test = AsyncRelationshipTo("SomeModel", "SELF")


def test_len_relationship():
    t1 = SomeModel().save()
    t2 = SomeModel().save()

    t1.test.connect(t2)
    l = len(t1.test.all())

    assert l
    assert l == 1
