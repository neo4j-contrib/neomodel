from datetime import date, datetime, timedelta
from test._async_compat import mark_async_test

from neo4j import time
from pytest import mark, raises
from pytz import timezone

from neomodel import (
    AsyncRelationship,
    AsyncStructuredNode,
    AsyncStructuredRel,
    adb,
    config,
)
from neomodel.contrib import AsyncSemiStructuredNode
from neomodel.exceptions import (
    DeflateError,
    InflateError,
    RequiredProperty,
    UniqueProperty,
)
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
    UniqueIdProperty,
    validator,
)
from neomodel.util import get_graph_entity_properties


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


@mark_async_test
async def test_string_property_w_choice():
    class TestChoices(AsyncStructuredNode):
        SEXES = {"F": "Female", "M": "Male", "O": "Other"}
        sex = StringProperty(required=True, choices=SEXES)

    try:
        await TestChoices(sex="Z").save()
    except DeflateError as e:
        assert "choice" in str(e)
    else:
        assert False, "DeflateError not raised."

    node = await TestChoices(sex="M").save()
    assert node.get_sex_display() == "Male"

    with raises(ValueError):

        class WrongChoices(AsyncStructuredNode):
            WRONG = "wrong"
            wrong_prop = StringProperty(choices=WRONG)


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

    with raises(ValueError, match="too many defaults"):
        _ = DateTimeFormatProperty(
            default_now=True, default=datetime(1900, 1, 1, 0, 0, 0)
        )

    prev_force_timezone = config.FORCE_TIMEZONE
    config.FORCE_TIMEZONE = True
    with raises(ValueError, match=r".*No timezone provided."):
        prop.deflate(datetime.now())

    config.FORCE_TIMEZONE = prev_force_timezone


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


@mark_async_test
async def test_default_value():
    class DefaultTestValue(AsyncStructuredNode):
        name_xx = StringProperty(default="jim", index=True)

    a = DefaultTestValue()
    assert a.name_xx == "jim"
    await a.save()


@mark_async_test
async def test_default_value_callable():
    def uid_generator():
        return "xx"

    class DefaultTestValueTwo(AsyncStructuredNode):
        uid = StringProperty(default=uid_generator, index=True)

    a = await DefaultTestValueTwo().save()
    assert a.uid == "xx"


@mark_async_test
async def test_default_value_callable_type():
    # check our object gets converted to str without serializing and reload
    def factory():
        class Foo:
            def __str__(self):
                return "123"

        return Foo()

    class DefaultTestValueThree(AsyncStructuredNode):
        uid = StringProperty(default=factory, index=True)

    x = DefaultTestValueThree()
    assert x.uid == "123"
    await x.save()
    assert x.uid == "123"
    await x.refresh()
    assert x.uid == "123"


class TestDBNamePropertyRel(AsyncStructuredRel):
    known_for = StringProperty(db_property="knownFor")


# This must be defined outside of the test, otherwise the `Relationship` definition cannot look up
# `TestDBNamePropertyNode`
class TestDBNamePropertyNode(AsyncStructuredNode):
    name_ = StringProperty(db_property="name")
    knows = AsyncRelationship(
        "TestDBNamePropertyNode", "KNOWS", model=TestDBNamePropertyRel
    )


@mark_async_test
async def test_independent_property_name():
    # -- test node --
    x = TestDBNamePropertyNode()
    x.name_ = "jim"
    await x.save()

    # check database property name on low level
    results, meta = await adb.cypher_query("MATCH (n:TestDBNamePropertyNode) RETURN n")
    node_properties = get_graph_entity_properties(results[0][0])
    assert node_properties["name"] == "jim"
    assert "name_" not in node_properties

    # check python class property name at a high level
    assert not hasattr(x, "name")
    assert hasattr(x, "name_")
    assert (await TestDBNamePropertyNode.nodes.filter(name_="jim").all())[
        0
    ].name_ == x.name_
    assert (await TestDBNamePropertyNode.nodes.get(name_="jim")).name_ == x.name_

    # -- test relationship --

    r = await x.knows.connect(x)
    r.known_for = "10 years"
    await r.save()

    # check database property name on low level
    results, meta = await adb.cypher_query(
        "MATCH (:TestDBNamePropertyNode)-[r:KNOWS]->(:TestDBNamePropertyNode) RETURN r"
    )
    rel_properties = get_graph_entity_properties(results[0][0])
    assert rel_properties["knownFor"] == "10 years"
    assert not "known_for" in node_properties

    # check python class property name at a high level
    assert not hasattr(r, "knownFor")
    assert hasattr(r, "known_for")
    rel = await x.knows.relationship(x)
    assert rel.known_for == r.known_for


@mark_async_test
async def test_independent_property_name_for_semi_structured():
    class TestDBNamePropertySemiStructuredNode(AsyncSemiStructuredNode):
        title_ = StringProperty(db_property="title")

    semi = TestDBNamePropertySemiStructuredNode(title_="sir", extra="data")
    await semi.save()

    # check database property name on low level
    results, meta = await adb.cypher_query(
        "MATCH (n:TestDBNamePropertySemiStructuredNode) RETURN n"
    )
    node_properties = get_graph_entity_properties(results[0][0])
    assert node_properties["title"] == "sir"
    # assert "title_" not in node_properties
    assert node_properties["extra"] == "data"

    # check python class property name at a high level
    assert hasattr(semi, "title_")
    assert not hasattr(semi, "title")
    assert hasattr(semi, "extra")
    from_filter = (
        await TestDBNamePropertySemiStructuredNode.nodes.filter(title_="sir").all()
    )[0]
    assert from_filter.title_ == "sir"
    # assert not hasattr(from_filter, "title")
    assert from_filter.extra == "data"
    from_get = await TestDBNamePropertySemiStructuredNode.nodes.get(title_="sir")
    assert from_get.title_ == "sir"
    # assert not hasattr(from_get, "title")
    assert from_get.extra == "data"


@mark_async_test
async def test_independent_property_name_get_or_create():
    class TestNode(AsyncStructuredNode):
        uid = UniqueIdProperty()
        name_ = StringProperty(db_property="name", required=True)

    # create the node
    await TestNode.get_or_create({"uid": 123, "name_": "jim"})
    # test that the node is retrieved correctly
    x = (await TestNode.get_or_create({"uid": 123, "name_": "jim"}))[0]

    # check database property name on low level
    results, _ = await adb.cypher_query("MATCH (n:TestNode) RETURN n")
    node_properties = get_graph_entity_properties(results[0][0])
    assert node_properties["name"] == "jim"
    assert "name_" not in node_properties


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


@mark_async_test
async def test_uid_property():
    prop = UniqueIdProperty()
    prop.name = "uid"
    prop.owner = object()
    myuid = prop.default_value()
    assert len(myuid)

    class CheckMyId(AsyncStructuredNode):
        uid = UniqueIdProperty()

    cmid = await CheckMyId().save()
    assert len(cmid.uid)

    matched_exception = r".*argument ignored by.*"
    # Test ignored arguments
    with raises(ValueError, match=matched_exception):
        _ = UniqueIdProperty(required=False)

    with raises(ValueError, match=matched_exception):
        _ = UniqueIdProperty(unique_index=False)

    with raises(ValueError, match=matched_exception):
        _ = UniqueIdProperty(index=False)

    with raises(ValueError, match=matched_exception):
        _ = UniqueIdProperty(default="kakapo")


class ArrayProps(AsyncStructuredNode):
    uid = StringProperty(unique_index=True)
    untyped_arr = ArrayProperty()
    typed_arr = ArrayProperty(IntegerProperty())


@mark_async_test
async def test_array_properties():
    # untyped
    ap1 = await ArrayProps(uid="1", untyped_arr=["Tim", "Bob"]).save()
    assert "Tim" in ap1.untyped_arr
    ap1 = await ArrayProps.nodes.get(uid="1")
    assert "Tim" in ap1.untyped_arr

    # typed
    try:
        await ArrayProps(uid="2", typed_arr=["a", "b"]).save()
    except DeflateError as e:
        assert "unsaved node" in str(e)
    else:
        assert False, "DeflateError not raised."

    ap2 = await ArrayProps(uid="2", typed_arr=[1, 2]).save()
    assert 1 in ap2.typed_arr
    ap2 = await ArrayProps.nodes.get(uid="2")
    assert 2 in ap2.typed_arr

    class Kakapo:
        pass

    with raises(TypeError, match="Expecting neomodel Property"):
        ArrayProperty(Kakapo)

    with raises(TypeError, match="Cannot have nested ArrayProperty"):
        ArrayProperty(ArrayProperty())


def test_illegal_array_base_prop_raises():
    with raises(ValueError):
        ArrayProperty(StringProperty(index=True))


@mark_async_test
async def test_indexed_array():
    class IndexArray(AsyncStructuredNode):
        ai = ArrayProperty(unique_index=True)

    b = await IndexArray(ai=[1, 2]).save()
    c = await IndexArray.nodes.get(ai=[1, 2])
    assert b.element_id == c.element_id


@mark_async_test
async def test_unique_index_prop_not_required():
    class ConstrainedTestNode(AsyncStructuredNode):
        required_property = StringProperty(required=True)
        unique_property = StringProperty(unique_index=True)
        unique_required_property = StringProperty(unique_index=True, required=True)
        unconstrained_property = StringProperty()

    # Create a node with a missing required property
    with raises(RequiredProperty):
        x = ConstrainedTestNode(required_property="required", unique_property="unique")
        await x.save()

    # Create a node with a missing unique (but not required) property.
    x = ConstrainedTestNode()
    x.required_property = "required"
    x.unique_required_property = "unique and required"
    x.unconstrained_property = "no contraints"
    await x.save()

    # check database property name on low level
    results, meta = await adb.cypher_query("MATCH (n:ConstrainedTestNode) RETURN n")
    node_properties = get_graph_entity_properties(results[0][0])
    assert node_properties["unique_required_property"] == "unique and required"


@mark_async_test
async def test_unique_index_prop_enforced():
    class UniqueNullableNameNode(AsyncStructuredNode):
        name = StringProperty(unique_index=True)

    await adb.install_labels(UniqueNullableNameNode)
    # Nameless
    x = UniqueNullableNameNode()
    await x.save()
    y = UniqueNullableNameNode()
    await y.save()

    # Named
    z = UniqueNullableNameNode(name="named")
    await z.save()
    with raises(UniqueProperty):
        a = UniqueNullableNameNode(name="named")
        await a.save()

    # Check nodes are in database
    results, _ = await adb.cypher_query("MATCH (n:UniqueNullableNameNode) RETURN n")
    assert len(results) == 3


def test_alias_property():
    class AliasedClass(AsyncStructuredNode):
        name = StringProperty(index=True)
        national_id = IntegerProperty(unique_index=True)
        alias = AliasProperty(to="name")
        alias_national_id = AliasProperty(to="national_id")
        whatever = StringProperty()
        alias_whatever = AliasProperty(to="whatever")

    assert AliasedClass.alias.index is True
    assert AliasedClass.alias_national_id.unique_index is True
    assert AliasedClass.alias_whatever.index is False
