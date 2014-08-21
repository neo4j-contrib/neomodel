from neomodel import (StructuredNode, StringProperty, IntegerProperty, ArrayProperty)
from neomodel.exception import RequiredProperty, UniqueProperty


class User(StructuredNode):
    email = StringProperty(unique_index=True, required=True)
    age = IntegerProperty(index=True)
    aliases = ArrayProperty()

    @property
    def email_alias(self):
        return self.email

    @email_alias.setter # noqa
    def email_alias(self, value):
        self.email = value


def test_array_properties():
    user = User(email='foo@bar.com', aliases=['Tim', 'Bob']).save()
    assert user
    assert 'Tim' in user.aliases
    user = User.nodes.get(email='foo@bar.com')
    assert user
    assert 'Tim' in user.aliases


def test_issue_72():
    user = User(email='foo@bar.com')
    assert user.age is None


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
    rob = User.nodes.get(email='robin@test.com')
    assert rob.email == 'robin@test.com'
    assert rob.age == 3


def test_save_to_model():
    u = User(email='jim@test.com', age=3)
    assert u.save()
    assert u._id > 0
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
    jim = User.nodes.get(email='jim2000@test.com')
    assert jim
    assert jim.email == 'jim2000@test.com'


def test_save_through_magic_property():
    user = User(email_alias='blah@test.com', age=8).save()
    assert user.email_alias == 'blah@test.com'
    user = User.nodes.get(email='blah@test.com')
    assert user.email == 'blah@test.com'
    assert user.email_alias == 'blah@test.com'

    user1 = User(email='blah1@test.com', age=8).save()
    assert user1.email_alias == 'blah1@test.com'
    user1.email_alias = 'blah2@test.com'
    assert user1.save()
    user2 = User.nodes.get(email='blah2@test.com')
    assert user2


class Customer2(StructuredNode):
    __label__ = 'customers'
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
    customers = Customer2.nodes.all()
    assert customers[0].email != customers[1].email
    assert Customer2.nodes.get(email='jim@bob.com').age == 7
    assert Customer2.nodes.get(email='jim1@bob.com').age == 2


def test_label_not_inherited():
    class Customer3(Customer2):
        address = StringProperty()

    assert Customer3.__label__ == 'Customer3'
    c = Customer3(email='test@test.com').save()
    assert 'customers' in c.labels()
    assert 'Customer3' in c.labels()

    c = Customer2.nodes.get(email='test@test.com')
    assert isinstance(c, Customer2)
    assert 'customers' in c.labels()
    assert 'Customer3' in c.labels()


def test_refresh():
    c = Customer2(email='my@email.com', age=16).save()
    c.my_custom_prop = 'value'
    copy = Customer2.nodes.get(email='my@email.com')
    copy.age = 20
    copy.save()

    assert c.age == 16

    c.refresh()
    assert c.age == 20
    assert c.my_custom_prop == 'value'
