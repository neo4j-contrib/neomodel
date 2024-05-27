from test._async_compat import mark_async_test

import pytest
from pytest import raises

from neomodel import (
    AsyncStructuredNode,
    IntegerProperty,
    StringProperty,
    UniqueProperty,
    adb,
)
from neomodel.exceptions import ConstraintValidationFailed


class Human(AsyncStructuredNode):
    name = StringProperty(unique_index=True)
    age = IntegerProperty(index=True)


@mark_async_test
async def test_unique_error():
    await adb.install_labels(Human)
    await Human(name="j1m", age=13).save()
    try:
        await Human(name="j1m", age=14).save()
    except UniqueProperty as e:
        assert str(e).find("j1m")
        assert str(e).find("name")
    else:
        assert False, "UniqueProperty not raised."


@mark_async_test
async def test_existence_constraint_error():
    if not await adb.edition_is_enterprise():
        pytest.skip("Skipping test for community edition")
    await adb.cypher_query(
        "CREATE CONSTRAINT test_existence_constraint FOR (n:Human) REQUIRE n.age IS NOT NULL"
    )
    with raises(ConstraintValidationFailed, match=r"must have the property"):
        await Human(name="Scarlett").save()

    await adb.cypher_query("DROP CONSTRAINT test_existence_constraint")


@mark_async_test
async def test_optional_properties_dont_get_indexed():
    await Human(name="99", age=99).save()
    h = await Human.nodes.get(age=99)
    assert h
    assert h.name == "99"

    await Human(name="98", age=98).save()
    h = await Human.nodes.get(age=98)
    assert h
    assert h.name == "98"


@mark_async_test
async def test_escaped_chars():
    _name = "sarah:test"
    await Human(name=_name, age=3).save()
    r = await Human.nodes.filter(name=_name)
    assert r[0].name == _name


@mark_async_test
async def test_does_not_exist():
    with raises(Human.DoesNotExist):
        await Human.nodes.get(name="XXXX")


@mark_async_test
async def test_custom_label_name():
    class Giraffe(AsyncStructuredNode):
        __label__ = "Giraffes"
        name = StringProperty(unique_index=True)

    jim = await Giraffe(name="timothy").save()
    node = await Giraffe.nodes.get(name="timothy")
    assert node.name == jim.name

    class SpecialGiraffe(Giraffe):
        power = StringProperty()

    # custom labels aren't inherited
    assert SpecialGiraffe.__label__ == "SpecialGiraffe"
