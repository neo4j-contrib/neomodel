from neomodel.properties import IntegerProperty
from neomodel.exception import InflateError, DeflateError


class FooBar(object):
    pass


def test_deflate_inflate():
    prop = IntegerProperty(required=True)
    prop.name = 'age'
    prop.owner = FooBar

    try:
        prop.inflate("six")
    except InflateError as e:
        assert True
        assert str(e).index('inflate property')
    else:
        assert False

    try:
        prop.deflate("six")
    except DeflateError as e:
        assert True
        assert str(e).index('deflate property')
    else:
        assert False
