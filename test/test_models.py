from __future__ import print_function

from datetime import datetime

from pytest import raises

from neomodel import (
    DateProperty,
    IntegerProperty,
    StringProperty,
    StructuredNode,
    StructuredRel,
    install_labels,
)
from neomodel.core import db
from neomodel.exceptions import RequiredProperty, UniqueProperty


class User(StructuredNode):
    email = StringProperty(unique_index=True, required=True)
    age = IntegerProperty(index=True)

    @property
    def email_alias(self):
        return self.email

    @email_alias.setter  # noqa
    def email_alias(self, value):
        self.email = value


class NodeWithoutProperty(StructuredNode):
    pass


def test_issue_233():
    class BaseIssue233(StructuredNode):
        __abstract_node__ = True

        def __getitem__(self, item):
            return self.__dict__[item]

    class Issue233(BaseIssue233):
        uid = StringProperty(unique_index=True, required=True)

    i = Issue233(uid="testgetitem").save()
    assert i["uid"] == "testgetitem"


def test_issue_72():
    user = User(email="foo@bar.com")
    assert user.age is None


def test_required():
    try:
        User(age=3).save()
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
    assert u.save()
    rob = User.nodes.get(email="robin@test.com")
    assert rob.email == "robin@test.com"
    assert rob.age == 3

    rob = User.nodes.get_or_none(email="robin@test.com")
    assert rob.email == "robin@test.com"

    n = User.nodes.get_or_none(email="robin@nothere.com")
    assert n is None


def test_first_and_first_or_none():
    u = User(email="matt@test.com", age=24)
    assert u.save()
    u2 = User(email="tbrady@test.com", age=40)
    assert u2.save()
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
    assert(User().element_id is None)


def test_save_to_model():
    u = User(email="jim@test.com", age=3)
    assert u.save()
    assert u.element_id is not None
    assert u.email == "jim@test.com"
    assert u.age == 3


def test_save_node_without_properties():
    n = NodeWithoutProperty()
    assert n.save()
    assert n.element_id is not None


def test_unique():
    install_labels(User)
    User(email="jim1@test.com", age=3).save()
    with raises(UniqueProperty):
        User(email="jim1@test.com", age=3).save()


def test_update_unique():
    u = User(email="jimxx@test.com", age=3).save()
    u.save()  # this shouldn't fail


def test_update():
    user = User(email="jim2@test.com", age=3).save()
    assert user
    user.email = "jim2000@test.com"
    user.save()
    jim = User.nodes.get(email="jim2000@test.com")
    assert jim
    assert jim.email == "jim2000@test.com"


def test_save_through_magic_property():
    user = User(email_alias="blah@test.com", age=8).save()
    assert user.email_alias == "blah@test.com"
    user = User.nodes.get(email="blah@test.com")
    assert user.email == "blah@test.com"
    assert user.email_alias == "blah@test.com"

    user1 = User(email="blah1@test.com", age=8).save()
    assert user1.email_alias == "blah1@test.com"
    user1.email_alias = "blah2@test.com"
    assert user1.save()
    user2 = User.nodes.get(email="blah2@test.com")
    assert user2


class Customer2(StructuredNode):
    __label__ = "customers"
    email = StringProperty(unique_index=True, required=True)
    age = IntegerProperty(index=True)


def test_not_updated_on_unique_error():
    install_labels(Customer2)
    Customer2(email="jim@bob.com", age=7).save()
    test = Customer2(email="jim1@bob.com", age=2).save()
    test.email = "jim@bob.com"
    with raises(UniqueProperty):
        test.save()
    customers = Customer2.nodes.all()
    assert customers[0].email != customers[1].email
    assert Customer2.nodes.get(email="jim@bob.com").age == 7
    assert Customer2.nodes.get(email="jim1@bob.com").age == 2


def test_label_not_inherited():
    class Customer3(Customer2):
        address = StringProperty()

    assert Customer3.__label__ == "Customer3"
    c = Customer3(email="test@test.com").save()
    assert "customers" in c.labels()
    assert "Customer3" in c.labels()

    c = Customer2.nodes.get(email="test@test.com")
    assert isinstance(c, Customer2)
    assert "customers" in c.labels()
    assert "Customer3" in c.labels()


def test_refresh():
    c = Customer2(email="my@email.com", age=16).save()
    c.my_custom_prop = "value"
    copy = Customer2.nodes.get(email="my@email.com")
    copy.age = 20
    copy.save()

    assert c.age == 16

    c.refresh()
    assert c.age == 20
    assert c.my_custom_prop == "value"

    c = Customer2.inflate(c.element_id)
    c.age = 30
    c.refresh()

    assert c.age == 20

    if db.database_version.startswith("4"):
        c = Customer2.inflate(999)
    else:
        c = Customer2.inflate("4:xxxxxx:999")
    with raises(Customer2.DoesNotExist):
        c.refresh()


def test_setting_value_to_none():
    c = Customer2(email="alice@bob.com", age=42).save()
    assert c.age is not None

    c.age = None
    c.save()

    copy = Customer2.nodes.get(email="alice@bob.com")
    assert copy.age is None


def test_inheritance():
    class User(StructuredNode):
        __abstract_node__ = True
        name = StringProperty(unique_index=True)

    class Shopper(User):
        balance = IntegerProperty(index=True)

        def credit_account(self, amount):
            self.balance = self.balance + int(amount)
            self.save()

    jim = Shopper(name="jimmy", balance=300).save()
    jim.credit_account(50)

    assert Shopper.__label__ == "Shopper"
    assert jim.balance == 350
    assert len(jim.inherited_labels()) == 1
    assert len(jim.labels()) == 1
    assert jim.labels()[0] == "Shopper"


def test_inherited_optional_labels():
    class BaseOptional(StructuredNode):
        __optional_labels__ = ["Alive"]
        name = StringProperty(unique_index=True)

    class ExtendedOptional(BaseOptional):
        __optional_labels__ = ["RewardsMember"]
        balance = IntegerProperty(index=True)

        def credit_account(self, amount):
            self.balance = self.balance + int(amount)
            self.save()

    henry = ExtendedOptional(name="henry", balance=300).save()
    henry.credit_account(50)

    assert ExtendedOptional.__label__ == "ExtendedOptional"
    assert henry.balance == 350
    assert len(henry.inherited_labels()) == 2
    assert len(henry.labels()) == 2

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

    class Shopper2(StructuredNode, UserMixin, CreditMixin):
        pass

    jim = Shopper2(name="jimmy", balance=300).save()
    jim.credit_account(50)

    assert Shopper2.__label__ == "Shopper2"
    assert jim.balance == 350
    assert len(jim.inherited_labels()) == 1
    assert len(jim.labels()) == 1
    assert jim.labels()[0] == "Shopper2"


def test_date_property():
    class DateTest(StructuredNode):
        birthdate = DateProperty()

    user = DateTest(birthdate=datetime.now()).save()


def test_reserved_property_keys():
    error_match = r".*is not allowed as it conflicts with neomodel internals.*"
    with raises(ValueError, match=error_match):

        class ReservedPropertiesDeletedNode(StructuredNode):
            deleted = StringProperty()

    with raises(ValueError, match=error_match):

        class ReservedPropertiesIdNode(StructuredNode):
            id = StringProperty()

    with raises(ValueError, match=error_match):

        class ReservedPropertiesElementIdNode(StructuredNode):
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
