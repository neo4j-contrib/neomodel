from test._async_compat import mark_sync_test

import pytest
from pytest import raises

from neomodel import IntegerProperty, StringProperty, StructuredNode, UniqueProperty, db
from neomodel.exceptions import ConstraintValidationFailed


class Human(StructuredNode):
    name = StringProperty(unique_index=True)
    age = IntegerProperty(index=True)


@mark_sync_test
def test_unique_error():
    db.install_labels(Human)
    Human(name="j1m", age=13).save()
    try:
        Human(name="j1m", age=14).save()
    except UniqueProperty as e:
        assert str(e).find("j1m")
        assert str(e).find("name")
    else:
        assert False, "UniqueProperty not raised."


@mark_sync_test
def test_existence_constraint_error():
    if not db.edition_is_enterprise():
        pytest.skip("Skipping test for community edition")
    db.cypher_query(
        "CREATE CONSTRAINT test_existence_constraint FOR (n:Human) REQUIRE n.age IS NOT NULL"
    )
    with raises(ConstraintValidationFailed, match=r"must have the property"):
        Human(name="Scarlett").save()

    db.cypher_query("DROP CONSTRAINT test_existence_constraint")


@mark_sync_test
def test_optional_properties_dont_get_indexed():
    Human(name="99", age=99).save()
    h = Human.nodes.get(age=99)
    assert h
    assert h.name == "99"

    Human(name="98", age=98).save()
    h = Human.nodes.get(age=98)
    assert h
    assert h.name == "98"


@mark_sync_test
def test_escaped_chars():
    _name = "sarah:test"
    Human(name=_name, age=3).save()
    r = Human.nodes.filter(name=_name)
    assert r[0].name == _name


@mark_sync_test
def test_does_not_exist():
    with raises(Human.DoesNotExist):
        Human.nodes.get(name="XXXX")


@mark_sync_test
def test_custom_label_name():
    class Giraffe(StructuredNode):
        __label__ = "Giraffes"
        name = StringProperty(unique_index=True)

    jim = Giraffe(name="timothy").save()
    node = Giraffe.nodes.get(name="timothy")
    assert node.name == jim.name

    class SpecialGiraffe(Giraffe):
        power = StringProperty()

    # custom labels aren't inherited
    assert SpecialGiraffe.__label__ == "SpecialGiraffe"
