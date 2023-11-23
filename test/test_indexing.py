import pytest
from pytest import raises

from neomodel import (
    IntegerProperty,
    StringProperty,
    StructuredNodeAsync,
    UniqueProperty,
)
from neomodel._async.core import adb
from neomodel.exceptions import ConstraintValidationFailed


class Human(StructuredNodeAsync):
    name = StringProperty(unique_index=True)
    age = IntegerProperty(index=True)


def test_unique_error():
    adb.install_labels_async(Human)
    Human(name="j1m", age=13).save_async()
    try:
        Human(name="j1m", age=14).save_async()
    except UniqueProperty as e:
        assert str(e).find("j1m")
        assert str(e).find("name")
    else:
        assert False, "UniqueProperty not raised."


@pytest.mark.skipif(
    not adb.edition_is_enterprise(), reason="Skipping test for community edition"
)
def test_existence_constraint_error():
    adb.cypher_query_async(
        "CREATE CONSTRAINT test_existence_constraint FOR (n:Human) REQUIRE n.age IS NOT NULL"
    )
    with raises(ConstraintValidationFailed, match=r"must have the property"):
        Human(name="Scarlett").save_async()

    adb.cypher_query_async("DROP CONSTRAINT test_existence_constraint")


def test_optional_properties_dont_get_indexed():
    Human(name="99", age=99).save_async()
    h = Human.nodes.get(age=99)
    assert h
    assert h.name == "99"

    Human(name="98", age=98).save_async()
    h = Human.nodes.get(age=98)
    assert h
    assert h.name == "98"


def test_escaped_chars():
    _name = "sarah:test"
    Human(name=_name, age=3).save_async()
    r = Human.nodes.filter(name=_name)
    assert r
    assert r[0].name == _name


def test_does_not_exist():
    with raises(Human.DoesNotExist):
        Human.nodes.get(name="XXXX")


def test_custom_label_name():
    class Giraffe(StructuredNodeAsync):
        __label__ = "Giraffes"
        name = StringProperty(unique_index=True)

    jim = Giraffe(name="timothy").save_async()
    node = Giraffe.nodes.get(name="timothy")
    assert node.name == jim.name

    class SpecialGiraffe(Giraffe):
        power = StringProperty()

    # custom labels aren't inherited
    assert SpecialGiraffe.__label__ == "SpecialGiraffe"
