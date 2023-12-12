from neomodel import AsyncStructuredNode, RelationshipTo


class SomeModel(AsyncStructuredNode):
    test = RelationshipTo("SomeModel", "SELF")


def test_len_relationship():
    t1 = SomeModel().save()
    t2 = SomeModel().save()

    t1.test.connect(t2)
    l = len(t1.test.all())

    assert l
    assert l == 1
