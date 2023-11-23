from __future__ import print_function

from datetime import datetime

from pytest import raises

from neomodel import (
    DateProperty,
    IntegerProperty,
    StringProperty,
    StructuredNodeAsync,
    StructuredRel,
)
from neomodel._async.core import adb
from neomodel.exceptions import RequiredProperty, UniqueProperty


class User(StructuredNodeAsync):
    email = StringProperty(unique_index=True, required=True)
    age = IntegerProperty(index=True)

    @property
    def email_alias(self):
        return self.email

    @email_alias.setter  # noqa
    def email_alias(self, value):
        self.email = value


class NodeWithoutProperty(StructuredNodeAsync):
    pass


def test_issue_233():
    class BaseIssue233(StructuredNodeAsync):
        __abstract_node__ = True

        def __getitem__(self, item):
            return self.__dict__[item]

    class Issue233(BaseIssue233):
        uid = StringProperty(unique_index=True, required=True)

    i = Issue233(uid="testgetitem").save_async()
    assert i["uid"] == "testgetitem"


def test_issue_72():
    user = User(email="foo@bar.com")
    assert user.age is None


def test_required():
    try:
        User(age=3).save_async()
    except RequiredProperty:
        assert True
    else:
        assert False


def test_repr_and_str():
    u = User(email="robin@test.com", age=3)
    print(repr(u))
    print(str(u))
    assert True


def test_get_and_get_or_none():
    u = User(email="robin@test.com", age=3)
    assert u.save_async()
    rob = User.nodes.get(email="robin@test.com")
    assert rob.email == "robin@test.com"
    assert rob.age == 3

    rob = User.nodes.get_or_none(email="robin@test.com")
    assert rob.email == "robin@test.com"

    n = User.nodes.get_or_none(email="robin@nothere.com")
    assert n is None


def test_first_and_first_or_none():
    u = User(email="matt@test.com", age=24)
    assert u.save_async()
    u2 = User(email="tbrady@test.com", age=40)
    assert u2.save_async()
    tbrady = User.nodes.order_by("-age").first()
    assert tbrady.email == "tbrady@test.com"
    assert tbrady.age == 40

    tbrady = User.nodes.order_by("-age").first_or_none()
    assert tbrady.email == "tbrady@test.com"

    n = User.nodes.first_or_none(email="matt@nothere.com")
    assert n is None


def test_bare_init_without_save():
    """
    If a node model is initialised without being saved, accessing its `element_id` should
    return None.
    """
    assert User().element_id is None


def test_save_to_model():
    u = User(email="jim@test.com", age=3)
    assert u.save_async()
    assert u.element_id is not None
    assert u.email == "jim@test.com"
    assert u.age == 3


def test_save_node_without_properties():
    n = NodeWithoutProperty()
    assert n.save_async()
    assert n.element_id is not None


def test_unique():
    adb.install_labels_async(User)
    User(email="jim1@test.com", age=3).save_async()
    with raises(UniqueProperty):
        User(email="jim1@test.com", age=3).save_async()


def test_update_unique():
    u = User(email="jimxx@test.com", age=3).save_async()
    u.save_async()  # this shouldn't fail


def test_update():
    user = User(email="jim2@test.com", age=3).save_async()
    assert user
    user.email = "jim2000@test.com"
    user.save_async()
    jim = User.nodes.get(email="jim2000@test.com")
    assert jim
    assert jim.email == "jim2000@test.com"


def test_save_through_magic_property():
    user = User(email_alias="blah@test.com", age=8).save_async()
    assert user.email_alias == "blah@test.com"
    user = User.nodes.get(email="blah@test.com")
    assert user.email == "blah@test.com"
    assert user.email_alias == "blah@test.com"

    user1 = User(email="blah1@test.com", age=8).save_async()
    assert user1.email_alias == "blah1@test.com"
    user1.email_alias = "blah2@test.com"
    assert user1.save_async()
    user2 = User.nodes.get(email="blah2@test.com")
    assert user2


class Customer2(StructuredNodeAsync):
    __label__ = "customers"
    email = StringProperty(unique_index=True, required=True)
    age = IntegerProperty(index=True)


def test_not_updated_on_unique_error():
    adb.install_labels_async(Customer2)
    Customer2(email="jim@bob.com", age=7).save_async()
    test = Customer2(email="jim1@bob.com", age=2).save_async()
    test.email = "jim@bob.com"
    with raises(UniqueProperty):
        test.save_async()
    customers = Customer2.nodes.all()
    assert customers[0].email != customers[1].email
    assert Customer2.nodes.get(email="jim@bob.com").age == 7
    assert Customer2.nodes.get(email="jim1@bob.com").age == 2


def test_label_not_inherited():
    class Customer3(Customer2):
        address = StringProperty()

    assert Customer3.__label__ == "Customer3"
    c = Customer3(email="test@test.com").save_async()
    assert "customers" in c.labels_async()
    assert "Customer3" in c.labels_async()

    c = Customer2.nodes.get(email="test@test.com")
    assert isinstance(c, Customer2)
    assert "customers" in c.labels_async()
    assert "Customer3" in c.labels_async()


def test_refresh():
    c = Customer2(email="my@email.com", age=16).save_async()
    c.my_custom_prop = "value"
    copy = Customer2.nodes.get(email="my@email.com")
    copy.age = 20
    copy.save()

    assert c.age == 16

    c.refresh_async()
    assert c.age == 20
    assert c.my_custom_prop == "value"

    c = Customer2.inflate(c.element_id)
    c.age = 30
    c.refresh_async()

    assert c.age == 20

    if adb.database_version.startswith("4"):
        c = Customer2.inflate(999)
    else:
        c = Customer2.inflate("4:xxxxxx:999")
    with raises(Customer2.DoesNotExist):
        c.refresh_async()


def test_setting_value_to_none():
    c = Customer2(email="alice@bob.com", age=42).save_async()
    assert c.age is not None

    c.age = None
    c.save_async()

    copy = Customer2.nodes.get(email="alice@bob.com")
    assert copy.age is None


def test_inheritance():
    class User(StructuredNodeAsync):
        __abstract_node__ = True
        name = StringProperty(unique_index=True)

    class Shopper(User):
        balance = IntegerProperty(index=True)

        def credit_account(self, amount):
            self.balance = self.balance + int(amount)
            self.save_async()

    jim = Shopper(name="jimmy", balance=300).save_async()
    jim.credit_account(50)

    assert Shopper.__label__ == "Shopper"
    assert jim.balance == 350
    assert len(jim.inherited_labels()) == 1
    assert len(jim.labels_async()) == 1
    assert jim.labels_async()[0] == "Shopper"


def test_inherited_optional_labels():
    class BaseOptional(StructuredNodeAsync):
        __optional_labels__ = ["Alive"]
        name = StringProperty(unique_index=True)

    class ExtendedOptional(BaseOptional):
        __optional_labels__ = ["RewardsMember"]
        balance = IntegerProperty(index=True)

        def credit_account(self, amount):
            self.balance = self.balance + int(amount)
            self.save_async()

    henry = ExtendedOptional(name="henry", balance=300).save_async()
    henry.credit_account(50)

    assert ExtendedOptional.__label__ == "ExtendedOptional"
    assert henry.balance == 350
    assert len(henry.inherited_labels()) == 2
    assert len(henry.labels_async()) == 2

    assert set(henry.inherited_optional_labels()) == {"Alive", "RewardsMember"}


def test_mixins():
    class UserMixin:
        name = StringProperty(unique_index=True)
        password = StringProperty()

    class CreditMixin:
        balance = IntegerProperty(index=True)

        def credit_account(self, amount):
            self.balance = self.balance + int(amount)
            self.save()

    class Shopper2(StructuredNodeAsync, UserMixin, CreditMixin):
        pass

    jim = Shopper2(name="jimmy", balance=300).save_async()
    jim.credit_account(50)

    assert Shopper2.__label__ == "Shopper2"
    assert jim.balance == 350
    assert len(jim.inherited_labels()) == 1
    assert len(jim.labels_async()) == 1
    assert jim.labels_async()[0] == "Shopper2"


def test_date_property():
    class DateTest(StructuredNodeAsync):
        birthdate = DateProperty()

    user = DateTest(birthdate=datetime.now()).save_async()


def test_reserved_property_keys():
    error_match = r".*is not allowed as it conflicts with neomodel internals.*"
    with raises(ValueError, match=error_match):

        class ReservedPropertiesDeletedNode(StructuredNodeAsync):
            deleted = StringProperty()

    with raises(ValueError, match=error_match):

        class ReservedPropertiesIdNode(StructuredNodeAsync):
            id = StringProperty()

    with raises(ValueError, match=error_match):

        class ReservedPropertiesElementIdNode(StructuredNodeAsync):
            element_id = StringProperty()

    with raises(ValueError, match=error_match):

        class ReservedPropertiesIdRel(StructuredRel):
            id = StringProperty()

    with raises(ValueError, match=error_match):

        class ReservedPropertiesElementIdRel(StructuredRel):
            element_id = StringProperty()

    error_match = r"Property names 'source' and 'target' are not allowed as they conflict with neomodel internals."
    with raises(ValueError, match=error_match):

        class ReservedPropertiesSourceRel(StructuredRel):
            source = StringProperty()

    with raises(ValueError, match=error_match):

        class ReservedPropertiesTargetRel(StructuredRel):
            target = StringProperty()
