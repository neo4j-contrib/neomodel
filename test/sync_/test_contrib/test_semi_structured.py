from test._async_compat import mark_sync_test

import pytest

from neomodel import (
    DeflateConflict,
    InflateConflict,
    IntegerProperty,
    StringProperty,
    db,
)
from neomodel.contrib import SemiStructuredNode


class UserProf(SemiStructuredNode):
    email = StringProperty(unique_index=True, required=True)
    age = IntegerProperty(index=True)


class Dummy(SemiStructuredNode):
    pass


@mark_sync_test
def test_to_save_to_model_with_required_only():
    u = UserProf(email="dummy@test.com")
    assert u.save()


@mark_sync_test
def test_save_to_model_with_extras():
    u = UserProf(email="jim@test.com", age=3, bar=99)
    u.foo = True
    assert u.save()
    u = UserProf.nodes.get(age=3)
    assert u.foo is True
    assert u.bar == 99


@mark_sync_test
def test_save_empty_model():
    dummy = Dummy()
    assert dummy.save()


@mark_sync_test
def test_inflate_conflict():
    class PersonForInflateTest(SemiStructuredNode):
        name = StringProperty()
        age = IntegerProperty()

        def hello(self):
            print("Hi my names " + self.name)

    # An ok model
    props = {"name": "Jim", "age": 8, "weight": 11}
    db.cypher_query("CREATE (n:PersonForInflateTest $props)", {"props": props})
    jim = PersonForInflateTest.nodes.get(name="Jim")
    assert jim.name == "Jim"
    assert jim.age == 8
    assert jim.weight == 11

    # A model that conflicts on `hello`
    props = {"name": "Tim", "age": 8, "hello": "goodbye"}
    db.cypher_query("CREATE (n:PersonForInflateTest $props)", {"props": props})
    with pytest.raises(InflateConflict):
        PersonForInflateTest.nodes.get(name="Tim")


@mark_sync_test
def test_deflate_conflict():
    class PersonForDeflateTest(SemiStructuredNode):
        name = StringProperty()
        age = IntegerProperty()

        def hello(self):
            print("Hi my names " + self.name)

    tim = PersonForDeflateTest(name="Tim", age=8, weight=11).save()
    tim.hello = "Hi"
    with pytest.raises(DeflateConflict):
        tim.save()
