from neomodel import RelationshipTo, StructuredNodeAsync


class SomeModel(StructuredNodeAsync):
    test = RelationshipTo("SomeModel", "SELF")


def test_len_relationship():
    t1 = SomeModel().save()
    t2 = SomeModel().save()

    t1.test.connect(t2)
    l = len(t1.test.all())

    assert l
    assert l == 1
