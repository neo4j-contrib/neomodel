from datetime import datetime
from test._async_compat import mark_async_test

from pytest import raises

from neomodel import (
    AsyncStructuredNode,
    AsyncStructuredRel,
    DateProperty,
    IntegerProperty,
    StringProperty,
    adb,
)
from neomodel.exceptions import RequiredProperty, UniqueProperty


class User(AsyncStructuredNode):
    email = StringProperty(unique_index=True, required=True)
    age = IntegerProperty(index=True)

    @property
    def email_alias(self):
        return self.email

    @email_alias.setter  # noqa
    def email_alias(self, value):
        self.email = value


class NodeWithoutProperty(AsyncStructuredNode):
    pass


@mark_async_test
async def test_issue_233():
    class BaseIssue233(AsyncStructuredNode):
        __abstract_node__ = True

        def __getitem__(self, item):
            return self.__dict__[item]

    class Issue233(BaseIssue233):
        uid = StringProperty(unique_index=True, required=True)

    i = await Issue233(uid="testgetitem").save()
    assert i["uid"] == "testgetitem"


def test_issue_72():
    user = User(email="foo@bar.com")
    assert user.age is None


@mark_async_test
async def test_required():
    with raises(RequiredProperty):
        await User(age=3).save()


def test_repr_and_str():
    u = User(email="robin@test.com", age=3)
    assert repr(u) == "<User: {'email': 'robin@test.com', 'age': 3}>"
    assert str(u) == "{'email': 'robin@test.com', 'age': 3}"


@mark_async_test
async def test_get_and_get_or_none():
    u = User(email="robin@test.com", age=3)
    assert await u.save()
    rob = await User.nodes.get(email="robin@test.com")
    assert rob.email == "robin@test.com"
    assert rob.age == 3

    rob = await User.nodes.get_or_none(email="robin@test.com")
    assert rob.email == "robin@test.com"

    n = await User.nodes.get_or_none(email="robin@nothere.com")
    assert n is None


@mark_async_test
async def test_first_and_first_or_none():
    u = User(email="matt@test.com", age=24)
    assert await u.save()
    u2 = User(email="tbrady@test.com", age=40)
    assert await u2.save()
    tbrady = await User.nodes.order_by("-age").first()
    assert tbrady.email == "tbrady@test.com"
    assert tbrady.age == 40

    tbrady = await User.nodes.order_by("-age").first_or_none()
    assert tbrady.email == "tbrady@test.com"

    n = await User.nodes.first_or_none(email="matt@nothere.com")
    assert n is None


def test_bare_init_without_save():
    """
    If a node model is initialised without being saved, accessing its `element_id` should
    return None.
    """
    assert User().element_id is None


@mark_async_test
async def test_save_to_model():
    u = User(email="jim@test.com", age=3)
    assert await u.save()
    assert u.element_id is not None
    assert u.email == "jim@test.com"
    assert u.age == 3


@mark_async_test
async def test_save_node_without_properties():
    n = NodeWithoutProperty()
    assert await n.save()
    assert n.element_id is not None


@mark_async_test
async def test_unique():
    await adb.install_labels(User)
    await User(email="jim1@test.com", age=3).save()
    with raises(UniqueProperty):
        await User(email="jim1@test.com", age=3).save()


@mark_async_test
async def test_update_unique():
    u = await User(email="jimxx@test.com", age=3).save()
    await u.save()  # this shouldn't fail


@mark_async_test
async def test_update():
    user = await User(email="jim2@test.com", age=3).save()
    assert user
    user.email = "jim2000@test.com"
    await user.save()
    jim = await User.nodes.get(email="jim2000@test.com")
    assert jim
    assert jim.email == "jim2000@test.com"


@mark_async_test
async def test_save_through_magic_property():
    user = await User(email_alias="blah@test.com", age=8).save()
    assert user.email_alias == "blah@test.com"
    user = await User.nodes.get(email="blah@test.com")
    assert user.email == "blah@test.com"
    assert user.email_alias == "blah@test.com"

    user1 = await User(email="blah1@test.com", age=8).save()
    assert user1.email_alias == "blah1@test.com"
    user1.email_alias = "blah2@test.com"
    assert await user1.save()
    user2 = await User.nodes.get(email="blah2@test.com")
    assert user2


class Customer2(AsyncStructuredNode):
    __label__ = "customers"
    email = StringProperty(unique_index=True, required=True)
    age = IntegerProperty(index=True)


@mark_async_test
async def test_not_updated_on_unique_error():
    await adb.install_labels(Customer2)
    await Customer2(email="jim@bob.com", age=7).save()
    test = await Customer2(email="jim1@bob.com", age=2).save()
    test.email = "jim@bob.com"
    with raises(UniqueProperty):
        await test.save()
    customers = await Customer2.nodes
    assert customers[0].email != customers[1].email
    assert (await Customer2.nodes.get(email="jim@bob.com")).age == 7
    assert (await Customer2.nodes.get(email="jim1@bob.com")).age == 2


@mark_async_test
async def test_label_not_inherited():
    class Customer3(Customer2):
        address = StringProperty()

    assert Customer3.__label__ == "Customer3"
    c = await Customer3(email="test@test.com").save()
    assert "customers" in await c.labels()
    assert "Customer3" in await c.labels()

    c = await Customer2.nodes.get(email="test@test.com")
    assert isinstance(c, Customer2)
    assert "customers" in await c.labels()
    assert "Customer3" in await c.labels()


@mark_async_test
async def test_refresh():
    c = await Customer2(email="my@email.com", age=16).save()
    c.my_custom_prop = "value"
    copy = await Customer2.nodes.get(email="my@email.com")
    copy.age = 20
    await copy.save()

    assert c.age == 16

    await c.refresh()
    assert c.age == 20
    assert c.my_custom_prop == "value"

    c = Customer2.inflate(c.element_id)
    c.age = 30
    await c.refresh()

    assert c.age == 20

    _db_version = await adb.database_version
    if _db_version.startswith("4"):
        c = Customer2.inflate(999)
    else:
        c = Customer2.inflate("4:xxxxxx:999")
    with raises(Customer2.DoesNotExist):
        await c.refresh()


@mark_async_test
async def test_setting_value_to_none():
    c = await Customer2(email="alice@bob.com", age=42).save()
    assert c.age is not None

    c.age = None
    await c.save()

    copy = await Customer2.nodes.get(email="alice@bob.com")
    assert copy.age is None


@mark_async_test
async def test_inheritance():
    class User(AsyncStructuredNode):
        __abstract_node__ = True
        name = StringProperty(unique_index=True)

    class Shopper(User):
        balance = IntegerProperty(index=True)

        async def credit_account(self, amount):
            self.balance = self.balance + int(amount)
            await self.save()

    jim = await Shopper(name="jimmy", balance=300).save()
    await jim.credit_account(50)

    assert Shopper.__label__ == "Shopper"
    assert jim.balance == 350
    assert len(jim.inherited_labels()) == 1
    assert len(await jim.labels()) == 1
    assert (await jim.labels())[0] == "Shopper"


@mark_async_test
async def test_inherited_optional_labels():
    class BaseOptional(AsyncStructuredNode):
        __optional_labels__ = ["Alive"]
        name = StringProperty(unique_index=True)

    class ExtendedOptional(BaseOptional):
        __optional_labels__ = ["RewardsMember"]
        balance = IntegerProperty(index=True)

        async def credit_account(self, amount):
            self.balance = self.balance + int(amount)
            await self.save()

    henry = await ExtendedOptional(name="henry", balance=300).save()
    await henry.credit_account(50)

    assert ExtendedOptional.__label__ == "ExtendedOptional"
    assert henry.balance == 350
    assert len(henry.inherited_labels()) == 2
    assert len(await henry.labels()) == 2

    assert set(henry.inherited_optional_labels()) == {"Alive", "RewardsMember"}


@mark_async_test
async def test_mixins():
    class UserMixin:
        name = StringProperty(unique_index=True)
        password = StringProperty()

    class CreditMixin:
        balance = IntegerProperty(index=True)

        async def credit_account(self, amount):
            self.balance = self.balance + int(amount)
            await self.save()

    class Shopper2(AsyncStructuredNode, UserMixin, CreditMixin):
        pass

    jim = await Shopper2(name="jimmy", balance=300).save()
    await jim.credit_account(50)

    assert Shopper2.__label__ == "Shopper2"
    assert jim.balance == 350
    assert len(jim.inherited_labels()) == 1
    assert len(await jim.labels()) == 1
    assert (await jim.labels())[0] == "Shopper2"


@mark_async_test
async def test_date_property():
    class DateTest(AsyncStructuredNode):
        birthdate = DateProperty()

    user = await DateTest(birthdate=datetime.now()).save()


def test_reserved_property_keys():
    error_match = r".*is not allowed as it conflicts with neomodel internals.*"
    with raises(ValueError, match=error_match):

        class ReservedPropertiesDeletedNode(AsyncStructuredNode):
            deleted = StringProperty()

    with raises(ValueError, match=error_match):

        class ReservedPropertiesIdNode(AsyncStructuredNode):
            id = StringProperty()

    with raises(ValueError, match=error_match):

        class ReservedPropertiesElementIdNode(AsyncStructuredNode):
            element_id = StringProperty()

    with raises(ValueError, match=error_match):

        class ReservedPropertiesIdRel(AsyncStructuredRel):
            id = StringProperty()

    with raises(ValueError, match=error_match):

        class ReservedPropertiesElementIdRel(AsyncStructuredRel):
            element_id = StringProperty()

    error_match = r"Property names 'source' and 'target' are not allowed as they conflict with neomodel internals."
    with raises(ValueError, match=error_match):

        class ReservedPropertiesSourceRel(AsyncStructuredRel):
            source = StringProperty()

    with raises(ValueError, match=error_match):

        class ReservedPropertiesTargetRel(AsyncStructuredRel):
            target = StringProperty()
