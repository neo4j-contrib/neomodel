from datetime import datetime, date

from pytest import mark, raises
from pytz import timezone

from neomodel import StructuredNode, db
from neomodel.exceptions import InflateError, DeflateError
from neomodel.properties import (
    ArrayProperty, IntegerProperty, DateProperty, DateTimeProperty,
    EmailProperty, JSONProperty, NormalProperty, NormalizedProperty,
    RegexProperty, StringProperty, UniqueIdProperty
)




class FooBar(object):
    pass


def test_string_property_w_choice():
    class TestChoices(StructuredNode):
        SEXES = {'F': 'Female', 'M': 'Male', 'O': 'Other'}
        sex = StringProperty(required=True, choices=SEXES)

    try:
        TestChoices(sex='Z').save()
    except DeflateError as e:
        assert 'choice' in str(e)
    else:
        assert False, "DeflateError not raised."

    node = TestChoices(sex='M').save()
    assert node.get_sex_display() == 'Male'


def test_deflate_inflate():
    prop = IntegerProperty(required=True)
    prop.name = 'age'
    prop.owner = FooBar

    try:
        prop.inflate("six")
    except InflateError as e:
        assert True
        assert 'inflate property' in str(e)
    else:
        assert False, "DeflateError not raised."

    try:
        prop.deflate("six")
    except DeflateError as e:
        assert 'deflate property' in str(e)
    else:
        assert False, "DeflateError not raised."


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
        assert 'inflate property' in str(e)
    else:
        assert False, "InflateError not raised."

    try:
        prop.deflate(faulty)
    except DeflateError as e:
        assert 'deflate property' in str(e)
    else:
        assert False, "DeflateError not raised."


def test_date_exceptions():
    prop = DateProperty()
    prop.name = 'date'
    prop.owner = FooBar
    faulty = '2012-14-13'

    try:
        prop.inflate(faulty)
    except InflateError as e:
        assert 'inflate property' in str(e)
    else:
        assert False, "InflateError not raised."

    try:
        prop.deflate(faulty)
    except DeflateError as e:
        assert 'deflate property' in str(e)
    else:
        assert False, "DeflateError not raised."


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


def test_independent_property_name():
    class TestNode(StructuredNode):
        name_ = StringProperty(db_property="name")
    x = TestNode()
    x.name_ = "jim"
    x.save()

    # check database property name on low level
    results, meta = db.cypher_query("MATCH (n:TestNode) RETURN n")
    assert results[0][0].properties['name'] == "jim"

    assert not 'name_' in results[0][0].properties
    assert not hasattr(x, 'name')
    assert hasattr(x, 'name_')
    assert TestNode.nodes.filter(name_="jim").all()[0].name_ == x.name_
    assert TestNode.nodes.get(name_="jim").name_ == x.name_

    x.delete()


def test_independent_property_name_get_or_create():
    class TestNode(StructuredNode):
        uid = UniqueIdProperty()
        name_ = StringProperty(db_property="name", required=True)

    # create the node
    TestNode.get_or_create({'uid': 123, 'name_': 'jim'})
    # test that the node is retrieved correctly
    x = TestNode.get_or_create({'uid': 123, 'name_': 'jim'})[0]

    # check database property name on low level
    results, meta = db.cypher_query("MATCH (n:TestNode) RETURN n")
    assert results[0][0].properties['name'] == "jim"
    assert 'name_' not in results[0][0].properties

    # delete node afterwards
    x.delete()


@mark.parametrize('normalized_class', (NormalizedProperty, NormalProperty))
def test_normalized_property(normalized_class):

    class TestProperty(normalized_class):
        def normalize(self, value):
            self._called_with = value
            self._called = True
            return value + 'bar'

    inflate = TestProperty()
    inflate_res = inflate.inflate('foo')
    assert getattr(inflate, '_called', False)
    assert getattr(inflate, '_called_with', None) == 'foo'
    assert inflate_res == 'foobar'

    deflate = TestProperty()
    deflate_res = deflate.deflate('bar')
    assert getattr(deflate, '_called', False)
    assert getattr(deflate, '_called_with', None) == 'bar'
    assert deflate_res == 'barbar'

    default = TestProperty(default='qux')
    default_res = default.default_value()
    assert getattr(default, '_called', False)
    assert getattr(default, '_called_with', None) == 'qux'
    assert default_res == 'quxbar'


def test_regex_property():
    class MissingExpression(RegexProperty):
        pass

    with raises(ValueError):
        MissingExpression()

    class TestProperty(RegexProperty):
        name = 'test'
        owner = object()
        expression = '\w+ \w+$'

        def normalize(self, value):
            self._called = True
            return super(TestProperty, self).normalize(value)

    prop = TestProperty()
    result = prop.inflate('foo bar')
    assert getattr(prop, '_called', False)
    assert result == 'foo bar'

    with raises(DeflateError):
        prop.deflate('qux')


def test_email_property():

    prop = EmailProperty()
    prop.name = 'email'
    prop.owner = object()
    result = prop.inflate('foo@example.com')
    assert result == 'foo@example.com'

    with raises(DeflateError):
        prop.deflate('foo@example')


def test_uid_property():
    prop = UniqueIdProperty()
    prop.name = 'uid'
    prop.owner = object()
    myuid = prop.default_value()
    assert len(myuid)

    class CheckMyId(StructuredNode):
        uid = UniqueIdProperty()

    cmid = CheckMyId().save()
    assert len(cmid.uid)


class ArrayProps(StructuredNode):
    uid = StringProperty(unique_index=True)
    untyped_arr = ArrayProperty()
    typed_arr = ArrayProperty(IntegerProperty())


def test_array_properties():
    # untyped
    ap1 = ArrayProps(uid='1', untyped_arr=['Tim', 'Bob']).save()
    assert 'Tim' in ap1.untyped_arr
    ap1 = ArrayProps.nodes.get(uid='1')
    assert 'Tim' in ap1.untyped_arr

    # typed
    try:
        ArrayProps(uid='2', typed_arr=['a', 'b']).save()
    except DeflateError as e:
        assert 'unsaved node' in str(e)
    else:
        assert False, "DeflateError not raised."

    ap2 = ArrayProps(uid='2', typed_arr=[1, 2]).save()
    assert 1 in ap2.typed_arr
    ap2 = ArrayProps.nodes.get(uid='2')
    assert 2 in ap2.typed_arr


def test_illegal_array_base_prop_raises():
    with raises(ValueError):
        ArrayProperty(StringProperty(index=True))


def test_indexed_array():
    class IndexArray(StructuredNode):
        ai = ArrayProperty(unique_index=True)

    b = IndexArray(ai=[1, 2]).save()
    c = IndexArray.nodes.get(ai=[1, 2])
    assert b.id == c.id
