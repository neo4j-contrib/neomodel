from neomodel import IntegerProperty, StringProperty
from neomodel.contrib import SemiStructuredNode


class UserProf(SemiStructuredNode):
    email = StringProperty(unique_index=True, required=True)
    age = IntegerProperty(index=True)


class Dummy(SemiStructuredNode):
    pass


def test_to_save_to_model_with_required_only():
    u = UserProf(email="dummy@test.com")
    assert u.save()


def test_save_to_model_with_extras():
    u = UserProf(email="jim@test.com", age=3, bar=99)
    u.foo = True
    assert u.save()
    u = UserProf.nodes.get(age=3)
    assert u.foo is True
    assert u.bar == 99


def test_save_empty_model():
    dummy = Dummy()
    assert dummy.save()
