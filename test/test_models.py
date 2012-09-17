from neomodel.core import NeoNode, StringProperty, IntegerProperty, connection_adapter


class User(NeoNode):
    email = StringProperty(unique_index=True)
    age = IntegerProperty(index=True)


def setup():
    connection_adapter().client.clear()
    User.deploy()


def test_get():
    u = User(email='robin@test.com', age=3)
    assert u.save()
    rob = User.get(email='robin@test.com')
    assert rob.email == 'robin@test.com'
    assert rob.age == 3


def test_find():
    assert User(email='robin1@test.com', age=3).save()
    assert User(email='robin2@test.com', age=3).save()
    users = User.search(age=3)
    assert len(users)


def test_save_to_model():
    u = User(email='jim@test.com', age=3)
    assert u.save()
    assert u._node
    assert u.email == 'jim@test.com'
    assert u.age == 3


def test_unique():
    User(email='jim1@test.com', age=3).save()
    try:
        User(email='jim1@test.com', age=3).save()
    except Exception, e:
        assert e.__class__.__name__ == 'NotUnique'


def test_update():
    user = User(email='jim2@test.com', age=3).save()
    assert user
    user.email = 'jim2000@test.com'
    user.save()
    jim = User.get(email='jim2000@test.com')
    assert jim
    assert jim.email == 'jim2000@test.com'


def teardown():
    connection_adapter().client.clear()
