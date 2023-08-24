from datetime import date, datetime

from pytest import mark, raises
from pytz import timezone

from neomodel import StructuredNode, config, db
from neomodel.exceptions import (
    DeflateError,
    InflateError,
    RequiredProperty,
    UniqueProperty,
)
from neomodel.properties import (
    ArrayProperty,
    DateProperty,
    DateTimeFormatProperty,
    DateTimeProperty,
    EmailProperty,
    IntegerProperty,
    JSONProperty,
    NormalizedProperty,
    RegexProperty,
    StringProperty,
    UniqueIdProperty,
)
from neomodel.util import _get_node_properties

config.AUTO_INSTALL_LABELS = True


class FooBar:
    pass


def test_string_property_exceeds_max_length():
    """
    StringProperty is defined by two properties: `max_length` and `choices` that are mutually exclusive. Furthermore,
    max_length must be a positive non-zero number.
    """
    # Try to define a property that has both choices and max_length
    with raises(ValueError):
        some_string_property = StringProperty(
            choices={"One": "1", "Two": "2"}, max_length=22
        )

    # Try to define a string property that has a negative zero length
    with raises(ValueError):
        another_string_property = StringProperty(max_length=-35)

    # Try to validate a long string
    a_string_property = StringProperty(required=True, max_length=5)
    with raises(ValueError):
        a_string_property.normalize("The quick brown fox jumps over the lazy dog")

    # Try to validate a "valid" string, as per the max_length setting.
    valid_string = "Owen"
    normalised_string = a_string_property.normalize(valid_string)
    assert (
        valid_string == normalised_string
    ), "StringProperty max_length test passed but values do not match."


def test_string_property_w_choice():
    class TestChoices(StructuredNode):
        SEXES = {"F": "Female", "M": "Male", "O": "Other"}
        sex = StringProperty(required=True, choices=SEXES)

    try:
        TestChoices(sex="Z").save()
    except DeflateError as e:
        assert "choice" in str(e)
    else:
        assert False, "DeflateError not raised."

    node = TestChoices(sex="M").save()
    assert node.get_sex_display() == "Male"


def test_deflate_inflate():
    prop = IntegerProperty(required=True)
    prop.name = "age"
    prop.owner = FooBar

    try:
        prop.inflate("six")
    except InflateError as e:
        assert True
        assert "inflate property" in str(e)
    else:
        assert False, "DeflateError not raised."

    try:
        prop.deflate("six")
    except DeflateError as e:
        assert "deflate property" in str(e)
    else:
        assert False, "DeflateError not raised."


def test_datetimes_timezones():
    prop = DateTimeProperty()
    prop.name = "foo"
    prop.owner = FooBar
    t = datetime.utcnow()
    gr = timezone("Europe/Athens")
    gb = timezone("Europe/London")
    dt1 = gr.localize(t)
    dt2 = gb.localize(t)
    time1 = prop.inflate(prop.deflate(dt1))
    time2 = prop.inflate(prop.deflate(dt2))
    assert time1.utctimetuple() == dt1.utctimetuple()
    assert time1.utctimetuple() < time2.utctimetuple()
    assert time1.tzname() == "UTC"


def test_date():
    prop = DateProperty()
    prop.name = "foo"
    prop.owner = FooBar
    somedate = date(2012, 12, 15)
    assert prop.deflate(somedate) == "2012-12-15"
    assert prop.inflate("2012-12-15") == somedate


def test_datetime_format():
    some_format = "%Y-%m-%d %H:%M:%S"
    prop = DateTimeFormatProperty(format=some_format)
    prop.name = "foo"
    prop.owner = FooBar
    some_datetime = datetime(2019, 3, 19, 15, 36, 25)
    assert prop.deflate(some_datetime) == "2019-03-19 15:36:25"
    assert prop.inflate("2019-03-19 15:36:25") == some_datetime


def test_datetime_exceptions():
    prop = DateTimeProperty()
    prop.name = "created"
    prop.owner = FooBar
    faulty = "dgdsg"

    try:
        prop.inflate(faulty)
    except InflateError as e:
        assert "inflate property" in str(e)
    else:
        assert False, "InflateError not raised."

    try:
        prop.deflate(faulty)
    except DeflateError as e:
        assert "deflate property" in str(e)
    else:
        assert False, "DeflateError not raised."


def test_date_exceptions():
    prop = DateProperty()
    prop.name = "date"
    prop.owner = FooBar
    faulty = "2012-14-13"

    try:
        prop.inflate(faulty)
    except InflateError as e:
        assert "inflate property" in str(e)
    else:
        assert False, "InflateError not raised."

    try:
        prop.deflate(faulty)
    except DeflateError as e:
        assert "deflate property" in str(e)
    else:
        assert False, "DeflateError not raised."


def test_json():
    prop = JSONProperty()
    prop.name = "json"
    prop.owner = FooBar

    value = {"test": [1, 2, 3]}

    assert prop.deflate(value) == '{"test": [1, 2, 3]}'
    assert prop.inflate('{"test": [1, 2, 3]}') == value


def test_default_value():
    class DefaultTestValue(StructuredNode):
        name_xx = StringProperty(default="jim", index=True)

    a = DefaultTestValue()
    assert a.name_xx == "jim"
    a.save()


def test_default_value_callable():
    def uid_generator():
        return "xx"

    class DefaultTestValueTwo(StructuredNode):
        uid = StringProperty(default=uid_generator, index=True)

    a = DefaultTestValueTwo().save()
    assert a.uid == "xx"


def test_default_value_callable_type():
    # check our object gets converted to str without serializing and reload
    def factory():
        class Foo:
            def __str__(self):
                return "123"

        return Foo()

    class DefaultTestValueThree(StructuredNode):
        uid = StringProperty(default=factory, index=True)

    x = DefaultTestValueThree()
    assert x.uid == "123"
    x.save()
    assert x.uid == "123"
    x.refresh()
    assert x.uid == "123"


def test_independent_property_name():
    class TestDBNamePropertyNode(StructuredNode):
        name_ = StringProperty(db_property="name")

    x = TestDBNamePropertyNode()
    x.name_ = "jim"
    x.save()

    # check database property name on low level
    results, meta = db.cypher_query("MATCH (n:TestDBNamePropertyNode) RETURN n")
    node_properties = _get_node_properties(results[0][0])
    assert node_properties["name"] == "jim"

    node_properties = _get_node_properties(results[0][0])
    assert not "name_" in node_properties
    assert not hasattr(x, "name")
    assert hasattr(x, "name_")
    assert TestDBNamePropertyNode.nodes.filter(name_="jim").all()[0].name_ == x.name_
    assert TestDBNamePropertyNode.nodes.get(name_="jim").name_ == x.name_

    x.delete()


def test_independent_property_name_get_or_create():
    class TestNode(StructuredNode):
        uid = UniqueIdProperty()
        name_ = StringProperty(db_property="name", required=True)

    # create the node
    TestNode.get_or_create({"uid": 123, "name_": "jim"})
    # test that the node is retrieved correctly
    x = TestNode.get_or_create({"uid": 123, "name_": "jim"})[0]

    # check database property name on low level
    results, meta = db.cypher_query("MATCH (n:TestNode) RETURN n")
    node_properties = _get_node_properties(results[0][0])
    assert node_properties["name"] == "jim"
    assert "name_" not in node_properties

    # delete node afterwards
    x.delete()


@mark.parametrize("normalized_class", (NormalizedProperty,))
def test_normalized_property(normalized_class):
    class TestProperty(normalized_class):
        def normalize(self, value):
            self._called_with = value
            self._called = True
            return value + "bar"

    inflate = TestProperty()
    inflate_res = inflate.inflate("foo")
    assert getattr(inflate, "_called", False)
    assert getattr(inflate, "_called_with", None) == "foo"
    assert inflate_res == "foobar"

    deflate = TestProperty()
    deflate_res = deflate.deflate("bar")
    assert getattr(deflate, "_called", False)
    assert getattr(deflate, "_called_with", None) == "bar"
    assert deflate_res == "barbar"

    default = TestProperty(default="qux")
    default_res = default.default_value()
    assert getattr(default, "_called", False)
    assert getattr(default, "_called_with", None) == "qux"
    assert default_res == "quxbar"


def test_regex_property():
    class MissingExpression(RegexProperty):
        pass

    with raises(ValueError):
        MissingExpression()

    class TestProperty(RegexProperty):
        name = "test"
        owner = object()
        expression = r"\w+ \w+$"

        def normalize(self, value):
            self._called = True
            return super().normalize(value)

    prop = TestProperty()
    result = prop.inflate("foo bar")
    assert getattr(prop, "_called", False)
    assert result == "foo bar"

    with raises(DeflateError):
        prop.deflate("qux")


def test_email_property():
    prop = EmailProperty()
    prop.name = "email"
    prop.owner = object()
    result = prop.inflate("foo@example.com")
    assert result == "foo@example.com"

    with raises(DeflateError):
        prop.deflate("foo@example")


def test_uid_property():
    prop = UniqueIdProperty()
    prop.name = "uid"
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
    ap1 = ArrayProps(uid="1", untyped_arr=["Tim", "Bob"]).save()
    assert "Tim" in ap1.untyped_arr
    ap1 = ArrayProps.nodes.get(uid="1")
    assert "Tim" in ap1.untyped_arr

    # typed
    try:
        ArrayProps(uid="2", typed_arr=["a", "b"]).save()
    except DeflateError as e:
        assert "unsaved node" in str(e)
    else:
        assert False, "DeflateError not raised."

    ap2 = ArrayProps(uid="2", typed_arr=[1, 2]).save()
    assert 1 in ap2.typed_arr
    ap2 = ArrayProps.nodes.get(uid="2")
    assert 2 in ap2.typed_arr


def test_illegal_array_base_prop_raises():
    with raises(ValueError):
        ArrayProperty(StringProperty(index=True))


def test_indexed_array():
    class IndexArray(StructuredNode):
        ai = ArrayProperty(unique_index=True)

    b = IndexArray(ai=[1, 2]).save()
    c = IndexArray.nodes.get(ai=[1, 2])
    assert b.element_id == c.element_id


def test_unique_index_prop_not_required():
    class ConstrainedTestNode(StructuredNode):
        required_property = StringProperty(required=True)
        unique_property = StringProperty(unique_index=True)
        unique_required_property = StringProperty(unique_index=True, required=True)
        unconstrained_property = StringProperty()

    # Create a node with a missing required property
    with raises(RequiredProperty):
        x = ConstrainedTestNode(required_property="required", unique_property="unique")
        x.save()

    # Create a node with a missing unique (but not required) property.
    x = ConstrainedTestNode()
    x.required_property = "required"
    x.unique_required_property = "unique and required"
    x.unconstrained_property = "no contraints"
    x.save()

    # check database property name on low level
    results, meta = db.cypher_query("MATCH (n:ConstrainedTestNode) RETURN n")
    node_properties = _get_node_properties(results[0][0])
    assert node_properties["unique_required_property"] == "unique and required"

    # delete node afterwards
    x.delete()


def test_unique_index_prop_enforced():
    class UniqueNullableNameNode(StructuredNode):
        name = StringProperty(unique_index=True)

    # Nameless
    x = UniqueNullableNameNode()
    x.save()
    y = UniqueNullableNameNode()
    y.save()

    # Named
    z = UniqueNullableNameNode(name="named")
    z.save()
    with raises(UniqueProperty):
        a = UniqueNullableNameNode(name="named")
        a.save()

    # Check nodes are in database
    results, meta = db.cypher_query("MATCH (n:UniqueNullableNameNode) RETURN n")
    assert len(results) == 3

    # Delete nodes afterwards
    x.delete()
    y.delete()
    z.delete()
