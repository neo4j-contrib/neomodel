from neomodel.properties import IntegerProperty, DateTimeProperty, DateProperty
from neomodel.exception import InflateError, DeflateError
from pytz import timezone
from datetime import datetime, date


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


def test_datetimes_timezones():
    prop = DateTimeProperty()
    prop.name = 'foo'
    prop.owner = FooBar
    t = datetime.utcnow()
    gr = timezone('Europe/Athens')
    gb = timezone('Europe/London')
    dt1 = gr.localize(t)
    dt2 = gb.localize(t)
    time1 = prop.inflate(prop.deflate(dt1))
    time2 = prop.inflate(prop.deflate(dt2))
    assert time1.utctimetuple() == dt1.utctimetuple()
    assert time1.utctimetuple() < time2.utctimetuple()
    assert time1.tzname() == 'UTC'


def test_datetime_no_timezone():
    prop = DateTimeProperty()
    prop.name = 'foo'
    prop.owner = FooBar
    try:
        prop.deflate(datetime.now())
    except DeflateError as e:
        assert str(e).index('have a timezone')
    else:
        assert False


def test_date():
    prop = DateProperty()
    prop.name = 'foo'
    prop.owner = FooBar
    somedate = date(2012, 12, 15)
    assert prop.deflate(somedate) == '2012-12-15'
    assert prop.inflate('2012-12-15') == somedate


def test_datetime_exceptions():
    prop = DateTimeProperty()
    prop.name = 'created'
    prop.owner = FooBar
    faulty = 'dgdsg'

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


def test_date_exceptions():
    prop = DateProperty()
    prop.name = 'date'
    prop.owner = FooBar
    faulty = '2012-14-13'

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
