from neomodel.properties import IntegerProperty, DatetimeProperty
from neomodel.exception import InflateError, DeflateError
from datetime import datetime


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


def test_datetime():
    prop = DatetimeProperty()
    prop.name = 'created'
    prop.owner = FooBar
    faulty = 'dgdsg'

    # Test simple case wrong object
    try:
        prop.inflate(faulty)
    except InflateError as e:
        assert True
        assert str(e).index('inflate property')
    else:
        assert False

    try:
        prop.deflate(faulty)
    except DeflateError as e:
        assert True
        assert str(e).index('deflate property')
    else:
        assert False

    # Test naive datetime
    naive = datetime.now()
    try:
        prop.deflate(naive)
    except DeflateError as e:
        assert True
        assert str(e).index('deflate property')
    else:
        assert False
