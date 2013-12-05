from neomodel import (StructuredNode, StringProperty, IntegerProperty)
from neomodel.exception import RequiredProperty, UniqueProperty


class User(StructuredNode):
    email = StringProperty(unique_index=True, required=True)
    age = IntegerProperty(index=True)

    @property
    def email_alias(self):
        return self.email

    @email_alias.setter
    def email_alias(self, value):
        self.email = value


def test_required():
    try:
        User(age=3).save()
    except RequiredProperty:
        assert True
    else:
        assert False


def test_get():
    u = User(email='robin@test.com', age=3)
    assert u.save()
    rob = User.index.get(email='robin@test.com')
    assert rob.email == 'robin@test.com'
    assert rob.age == 3


def test_search():
    assert User(email='robin1@test.com', age=3).save()
    assert User(email='robin2@test.com', age=3).save()
    users = User.index.search(age=3)
    assert len(users)


def test_save_to_model():
    u = User(email='jim@test.com', age=3)
    assert u.save()
    assert u.__node__ is not None
    assert u.email == 'jim@test.com'
    assert u.age == 3


def test_unique():
    User(email='jim1@test.com', age=3).save()
    try:
        User(email='jim1@test.com', age=3).save()
    except Exception as e:
        assert e.__class__.__name__ == 'UniqueProperty'
    else:
        assert False


def test_update_unique():
    u = User(email='jimxx@test.com', age=3).save()
    try:
        u.save() # this shouldn't fail
    except UniqueProperty:
        assert False
    else:
        assert True


def test_update():
    user = User(email='jim2@test.com', age=3).save()
    assert user
    user.email = 'jim2000@test.com'
    user.save()
    jim = User.index.get(email='jim2000@test.com')
    assert jim
    assert jim.email == 'jim2000@test.com'


def test_save_through_magic_property():
    user = User(email_alias='blah@test.com', age=8).save()
    assert user.email_alias == 'blah@test.com'
    user = User.index.get(email='blah@test.com')
    assert user.email == 'blah@test.com'
    assert user.email_alias == 'blah@test.com'

    user1 = User(email='blah1@test.com', age=8).save()
    assert user1.email_alias == 'blah1@test.com'
    user1.email_alias = 'blah2@test.com'
    assert user1.save()
    user2 = User.index.get(email='blah2@test.com')
    assert user2


class Customer2(StructuredNode):
    email = StringProperty(unique_index=True, required=True)
    age = IntegerProperty(index=True)


def test_not_updated_on_unique_error():
    Customer2(email='jim@bob.com', age=7).save()
    test = Customer2(email='jim1@bob.com', age=2).save()
    test.email = 'jim@bob.com'
    try:
        test.save()
    except UniqueProperty:
        pass
    customers = Customer2.category().instance.all()
    assert customers[0].email != customers[1].email
    assert Customer2.index.get(email='jim@bob.com').age == 7
    assert Customer2.index.get(email='jim1@bob.com').age == 2


def test_refresh():
    c = Customer2(email='my@email.com', age=16).save()
    c.my_custom_prop = 'value'
    copy = Customer2.index.get(email='my@email.com')
    copy.age = 20
    copy.save()

    assert c.age == 16

    c.refresh()
    assert c.age == 20
    assert c.my_custom_prop == 'value'
