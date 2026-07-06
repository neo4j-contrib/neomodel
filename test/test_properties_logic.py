"""
World-agnostic property logic tests.

These exercise the shared ``neomodel.properties`` descriptors (validation,
deflate/inflate, defaults) directly, without touching the database or the
async/sync split. They used to live in ``test/async_/test_properties.py`` and
were therefore transpiled and run twice (once per world) behind a live Neo4j
session, even though the behaviour under test is identical in both worlds and
needs no connection. They now run once here as plain sync unit tests.
"""

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from neo4j import time
from pytest import mark, raises

from neomodel import StructuredNode, get_config
from neomodel.exceptions import DeflateError, InflateError
from neomodel.properties import (
    AliasProperty,
    ArrayProperty,
    BooleanProperty,
    DateProperty,
    DateTimeFormatProperty,
    DateTimeNeo4jFormatProperty,
    DateTimeProperty,
    EmailProperty,
    IntegerProperty,
    JSONProperty,
    NormalizedProperty,
    RegexProperty,
    StringProperty,
    validator,
)


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


def test_deflate_inflate():
    prop = IntegerProperty(required=True)
    prop.name = "age"
    prop.owner = FooBar

    try:
        prop.inflate("six")
    except InflateError as e:
        assert "inflate property" in str(e)
    else:
        assert False, "DeflateError not raised."

    try:
        prop.deflate("six")
    except DeflateError as e:
        assert "deflate property" in str(e)
    else:
        assert False, "DeflateError not raised."

    with raises(ValueError, match="Unknown Property method tartiflate"):

        class CheeseProperty(IntegerProperty):
            @validator
            def tartiflate(self, value):
                return int(value)


def test_boolean_property():
    prop = BooleanProperty(default=False)
    prop.name = "foo"
    prop.owner = FooBar
    assert prop.deflate(True) is True
    assert prop.deflate(False) is False
    assert prop.inflate(True) is True
    assert prop.inflate(False) is False

    assert prop.default_value() is False


def test_datetimes_timezones():
    prop = DateTimeProperty()
    prop.name = "foo"
    prop.owner = FooBar
    t = datetime.now(timezone.utc)
    gr = ZoneInfo("Europe/Athens")
    gb = ZoneInfo("Europe/London")
    dt1 = t.replace(tzinfo=gr)
    dt2 = t.replace(tzinfo=gb)
    time1 = prop.inflate(prop.deflate(dt1))
    time2 = prop.inflate(prop.deflate(dt2))
    assert time1.utctimetuple() == dt1.utctimetuple()
    assert time1.utctimetuple() < time2.utctimetuple()
    assert time1.tzname() == "UTC"

    with raises(ValueError, match="too many defaults"):
        _ = DateTimeFormatProperty(
            default_now=True, default=datetime(1900, 1, 1, 0, 0, 0)
        )

    config = get_config()
    prev_force_timezone = config.force_timezone
    config.force_timezone = True
    with raises(ValueError, match=r".*No timezone provided."):
        prop.deflate(datetime.now())

    config.force_timezone = prev_force_timezone


def test_date():
    prop = DateProperty()
    prop.name = "foo"
    prop.owner = FooBar
    somedate = date(2012, 12, 15)
    assert prop.deflate(somedate) == "2012-12-15"
    assert prop.inflate("2012-12-15") == somedate

    assert prop.inflate(time.DateTime(2007, 9, 27)) == date(2007, 9, 27)


def test_datetime_format():
    some_format = "%Y-%m-%d %H:%M:%S"
    prop = DateTimeFormatProperty(format=some_format)
    prop.name = "foo"
    prop.owner = FooBar
    some_datetime = datetime(2019, 3, 19, 15, 36, 25)
    assert prop.deflate(some_datetime) == "2019-03-19 15:36:25"
    assert prop.inflate("2019-03-19 15:36:25") == some_datetime

    with raises(ValueError, match=r"datetime object expected, got.*"):
        prop.deflate(1234)

    with raises(ValueError, match="too many defaults"):
        _ = DateTimeFormatProperty(
            default_now=True, default=datetime(1900, 1, 1, 0, 0, 0)
        )

    secondProp = DateTimeFormatProperty(default_now=True)
    assert secondProp.has_default
    assert (
        timedelta(seconds=-2)
        < secondProp.default - datetime.now()
        < timedelta(seconds=2)
    )


def test_datetime_neo4j_format():
    prop = DateTimeNeo4jFormatProperty()
    prop.name = "foo"
    prop.owner = FooBar
    some_datetime = datetime(2022, 12, 10, 14, 00, 00)
    assert prop.has_default is False
    assert prop.default is None
    assert prop.deflate(some_datetime) == time.DateTime(2022, 12, 10, 14, 00, 00)
    assert prop.inflate(time.DateTime(2022, 12, 10, 14, 00, 00)) == some_datetime

    with raises(ValueError, match=r"datetime object expected, got.*"):
        prop.deflate(1234)

    with raises(ValueError, match="too many defaults"):
        _ = DateTimeNeo4jFormatProperty(
            default_now=True, default=datetime(1900, 1, 1, 0, 0, 0)
        )

    secondProp = DateTimeNeo4jFormatProperty(default_now=True)
    assert secondProp.has_default
    assert (
        timedelta(seconds=-2)
        < secondProp.default - datetime.now()
        < timedelta(seconds=2)
    )


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

    with raises(ValueError, match="too many defaults"):
        _ = DateTimeProperty(default_now=True, default=datetime(1900, 1, 1, 0, 0, 0))


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


def test_base_exceptions():
    # default-required conflict
    with raises(
        ValueError,
        match="The arguments `required` and `default` are mutually exclusive.",
    ):
        _ = StringProperty(default="kakapo", required=True)

    # unique_index - index conflict
    with raises(
        ValueError,
        match="The arguments `unique_index` and `index` are mutually exclusive.",
    ):
        _ = IntegerProperty(index=True, unique_index=True)

    # no default value
    kakapo = StringProperty()
    with raises(ValueError, match="No default value specified"):
        kakapo.default_value()

    # missing normalize method
    class WoopsProperty(NormalizedProperty):
        pass

    woops = WoopsProperty()
    with raises(NotImplementedError, match="Specialize normalize method"):
        woops.normalize("kakapo")


def test_json():
    prop = JSONProperty()
    prop.name = "json"
    prop.owner = FooBar

    value = {"test": [1, 2, 3]}

    assert prop.deflate(value) == '{"test": [1, 2, 3]}'
    assert prop.inflate('{"test": [1, 2, 3]}') == value

    value_with_unicode = {"test": [1, 2, 3, "©"]}
    assert prop.deflate(value_with_unicode) == '{"test": [1, 2, 3, "\\u00a9"]}'
    assert prop.inflate('{"test": [1, 2, 3, "\\u00a9"]}') == value_with_unicode


def test_json_unicode():
    prop = JSONProperty(ensure_ascii=False)
    prop.name = "json"
    prop.owner = FooBar

    value = {"test": [1, 2, 3, "©"]}

    assert prop.deflate(value) == '{"test": [1, 2, 3, "©"]}'
    assert prop.inflate('{"test": [1, 2, 3, "©"]}') == value


def test_indexed():
    indexed = StringProperty(index=True)
    assert indexed.is_indexed is True

    unique_indexed = StringProperty(unique_index=True)
    assert unique_indexed.is_indexed is True

    not_indexed = StringProperty()
    assert not_indexed.is_indexed is False


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

    with raises(AttributeError):
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


def test_illegal_array_base_prop_raises():
    with raises(ValueError):
        ArrayProperty(StringProperty(index=True))


def test_alias_property():
    class AliasedClass(StructuredNode):
        name = StringProperty(index=True)
        national_id = IntegerProperty(unique_index=True)
        alias = AliasProperty(to="name")
        alias_national_id = AliasProperty(to="national_id")
        whatever = StringProperty()
        alias_whatever = AliasProperty(to="whatever")

    assert AliasedClass.alias.index is True
    assert AliasedClass.alias_national_id.unique_index is True
    assert AliasedClass.alias_whatever.index is False
