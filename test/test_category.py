from neomodel import StructuredNode, StringProperty


class Giraffe(StructuredNode):
    name = StringProperty()


class Foobar(StructuredNode):
    name = StringProperty()


def test_category_node():
    Giraffe(name='Tim').save()
    Giraffe(name='Tim1').save()
    Giraffe(name='Tim2').save()
    z = Giraffe(name='Tim3').save()

    assert len(Giraffe.category().instance.all()) == 4

    # can't connect on category node
    try:
        Giraffe.category().instance.connect(z)
    except Exception:
        assert True
    else:
        assert False

    # can't disconnect on category node
    try:
        Giraffe.category().instance.disconnect(z)
    except Exception:
        assert True
    else:
        assert False

    results = Giraffe.category().instance.search(name='Tim')
    assert len(results) == 1
    assert results[0].name == 'Tim'


# doesn't bork if no category node
def test_no_category_node():
    assert len(Foobar.category().instance.all()) == 0
