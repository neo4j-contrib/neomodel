from neomodel.properties import (IntegerProperty, DateTimeProperty,
    DateProperty, StringProperty, JSONProperty)
from neomodel.exception import InflateError, DeflateError
from neomodel import StructuredNode
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


def test_json():
    prop = JSONProperty()
    prop.name = 'json'
    prop.owner = FooBar

    value = {'test': [1, 2, 3]}

    assert prop.deflate(value) == '{"test": [1, 2, 3]}'
    assert prop.inflate('{"test": [1, 2, 3]}') == value


def test_default_value():
    class DefaultTestValue(StructuredNode):
        name_xx = StringProperty(default='jim', index=True)

    a = DefaultTestValue()
    assert a.name_xx == 'jim'
    a.save()
    return
    b = DefaultTestValue.index.get(name='jim')
    assert b.name == 'jim'

    c = DefaultTestValue(name=None)
    assert c.name == 'jim'


def test_default_value_callable():
    def uid_generator():
        return 'xx'

    class DefaultTestValueTwo(StructuredNode):
        uid = StringProperty(default=uid_generator, index=True)

    a = DefaultTestValueTwo().save()
    assert a.uid == 'xx'


def test_default_valude_callable_type():
    # check our object gets converted to str without serializing and reload
    def factory():
        class Foo(object):
            def __str__(self):
                return "123"
        return Foo()

    class DefaultTestValueThree(StructuredNode):
        uid = StringProperty(default=factory, index=True)

    x = DefaultTestValueThree()
    assert x.uid == '123'
    x.save()
    assert x.uid == '123'
    x.refresh()
    assert x.uid == '123'
