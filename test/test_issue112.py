from neomodel import StructuredNode, RelationshipTo


class TestModel(StructuredNode):
    test = RelationshipTo('TestModel', 'SELF')


def test_len_relationship():
    t1 = TestModel().save()
    t2 = TestModel().save()

    t1.test.connect(t2)
    l = len(t1.test.all())

    assert l
    assert l == 1


if __name__ == '__main__':
    test_len_relationship()
