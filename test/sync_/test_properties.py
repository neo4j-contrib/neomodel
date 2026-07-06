from test._async_compat import mark_sync_test

from pytest import raises

from neomodel import Relationship, StructuredNode, StructuredRel, db
from neomodel.contrib import SemiStructuredNode
from neomodel.exceptions import DeflateError, RequiredProperty, UniqueProperty
from neomodel.properties import (
    ArrayProperty,
    IntegerProperty,
    StringProperty,
    UniqueIdProperty,
)
from neomodel.util import get_graph_entity_properties


@mark_sync_test
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

    with raises(ValueError):

        class WrongChoices(StructuredNode):
            WRONG = "wrong"
            wrong_prop = StringProperty(choices=WRONG)


@mark_sync_test
def test_default_value():
    class DefaultTestValue(StructuredNode):
        name_xx = StringProperty(default="jim", index=True)

    a = DefaultTestValue()
    assert a.name_xx == "jim"
    a.save()


@mark_sync_test
def test_default_value_callable():
    def uid_generator():
        return "xx"

    class DefaultTestValueTwo(StructuredNode):
        uid = StringProperty(default=uid_generator, index=True)

    a = DefaultTestValueTwo().save()
    assert a.uid == "xx"


@mark_sync_test
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


class DBNamePropertyRel(StructuredRel):
    known_for = StringProperty(db_property="knownFor")


# This must be defined outside of the test, otherwise the `Relationship` definition cannot look up
# `DBNamePropertyNode`
class DBNamePropertyNode(StructuredNode):
    name_ = StringProperty(db_property="name")
    knows = Relationship("DBNamePropertyNode", "KNOWS", model=DBNamePropertyRel)


@mark_sync_test
def test_independent_property_name():
    # -- test node --
    x = DBNamePropertyNode()
    x.name_ = "jim"
    x.save()

    # check database property name on low level
    results, meta = db.cypher_query("MATCH (n:DBNamePropertyNode) RETURN n")
    node_properties = get_graph_entity_properties(results[0][0])
    assert node_properties["name"] == "jim"
    assert "name_" not in node_properties

    # check python class property name at a high level
    assert not hasattr(x, "name")
    assert hasattr(x, "name_")
    assert (DBNamePropertyNode.nodes.filter(name_="jim").all())[0].name_ == x.name_
    assert (DBNamePropertyNode.nodes.get(name_="jim")).name_ == x.name_

    # -- test relationship --

    r = x.knows.connect(x)
    r.known_for = "10 years"
    r.save()

    # check database property name on low level
    results, meta = db.cypher_query(
        "MATCH (:DBNamePropertyNode)-[r:KNOWS]->(:DBNamePropertyNode) RETURN r"
    )
    rel_properties = get_graph_entity_properties(results[0][0])
    assert rel_properties["knownFor"] == "10 years"
    assert not "known_for" in node_properties

    # check python class property name at a high level
    assert not hasattr(r, "knownFor")
    assert hasattr(r, "known_for")
    rel = x.knows.relationship(x)
    assert rel.known_for == r.known_for


@mark_sync_test
def test_independent_property_name_for_semi_structured():
    class DBNamePropertySemiStructuredNode(SemiStructuredNode):
        title_ = StringProperty(db_property="title")

    semi = DBNamePropertySemiStructuredNode(title_="sir", extra="data")
    semi.save()

    # check database property name on low level
    results, meta = db.cypher_query(
        "MATCH (n:DBNamePropertySemiStructuredNode) RETURN n"
    )
    node_properties = get_graph_entity_properties(results[0][0])
    assert node_properties["title"] == "sir"
    # assert "title_" not in node_properties
    assert node_properties["extra"] == "data"

    # check python class property name at a high level
    assert hasattr(semi, "title_")
    assert not hasattr(semi, "title")
    assert hasattr(semi, "extra")
    from_filter = (DBNamePropertySemiStructuredNode.nodes.filter(title_="sir").all())[0]
    assert from_filter.title_ == "sir"
    # assert not hasattr(from_filter, "title")
    assert from_filter.extra == "data"
    from_get = DBNamePropertySemiStructuredNode.nodes.get(title_="sir")
    assert from_get.title_ == "sir"
    # assert not hasattr(from_get, "title")
    assert from_get.extra == "data"


@mark_sync_test
def test_independent_property_name_get_or_create():
    class TestNode(StructuredNode):
        uid = UniqueIdProperty()
        name_ = StringProperty(db_property="name", required=True)

    # create the node
    TestNode.get_or_create({"uid": 123, "name_": "jim"})
    # test that the node is retrieved correctly
    x = (TestNode.get_or_create({"uid": 123, "name_": "jim"}))[0]

    # check database property name on low level
    results, _ = db.cypher_query("MATCH (n:TestNode) RETURN n")
    node_properties = get_graph_entity_properties(results[0][0])
    assert node_properties["name"] == "jim"
    assert "name_" not in node_properties


@mark_sync_test
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


class ArrayProps(StructuredNode):
    uid = StringProperty(unique_index=True)
    untyped_arr = ArrayProperty()
    typed_arr = ArrayProperty(IntegerProperty())


@mark_sync_test
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

    class Kakapo:
        pass

    with raises(TypeError, match="Expecting neomodel Property"):
        ArrayProperty(Kakapo)

    with raises(TypeError, match="Cannot have nested ArrayProperty"):
        ArrayProperty(ArrayProperty())


@mark_sync_test
def test_indexed_array():
    class IndexArray(StructuredNode):
        ai = ArrayProperty(unique_index=True)

    b = IndexArray(ai=[1, 2]).save()
    c = IndexArray.nodes.get(ai=[1, 2])
    assert b.element_id == c.element_id


@mark_sync_test
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
    node_properties = get_graph_entity_properties(results[0][0])
    assert node_properties["unique_required_property"] == "unique and required"


@mark_sync_test
def test_unique_index_prop_enforced():
    class UniqueNullableNameNode(StructuredNode):
        name = StringProperty(unique_index=True)

    db.install_labels(UniqueNullableNameNode)
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
    results, _ = db.cypher_query("MATCH (n:UniqueNullableNameNode) RETURN n")
    assert len(results) == 3
