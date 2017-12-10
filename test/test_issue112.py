from neomodel import StructuredNode, RelationshipTo


class SomeModel(StructuredNode):
    test = RelationshipTo('SomeModel', 'SELF')


def test_len_relationship():
    t1 = SomeModel().save()
    t2 = SomeModel().save()

    t1.test.connect(t2)
    l = len(t1.test.all())

    assert l
    assert l == 1
