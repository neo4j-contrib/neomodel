from datetime import datetime
from test._async_compat import mark_async_test

import pytz
from pytest import raises

from neomodel import (
    AsyncRelationship,
    AsyncRelationshipTo,
    AsyncStructuredNode,
    AsyncStructuredRel,
    DateTimeProperty,
    DeflateError,
    StringProperty,
)
from neomodel._async_compat.util import AsyncUtil

HOOKS_CALLED = {"pre_save": 0, "post_save": 0}


class FriendRel(AsyncStructuredRel):
    since = DateTimeProperty(default=lambda: datetime.now(pytz.utc))


class HatesRel(FriendRel):
    reason = StringProperty()

    def pre_save(self):
        HOOKS_CALLED["pre_save"] += 1

    def post_save(self):
        HOOKS_CALLED["post_save"] += 1


class Badger(AsyncStructuredNode):
    name = StringProperty(unique_index=True)
    friend = AsyncRelationship("Badger", "FRIEND", model=FriendRel)
    hates = AsyncRelationshipTo("Stoat", "HATES", model=HatesRel)


class Stoat(AsyncStructuredNode):
    name = StringProperty(unique_index=True)
    hates = AsyncRelationshipTo("Badger", "HATES", model=HatesRel)


@mark_async_test
async def test_either_connect_with_rel_model():
    paul = await Badger(name="Paul").save()
    tom = await Badger(name="Tom").save()

    # creating rels
    new_rel = await tom.friend.disconnect(paul)
    new_rel = await tom.friend.connect(paul)
    assert isinstance(new_rel, FriendRel)
    assert isinstance(new_rel.since, datetime)

    # updating properties
    new_rel.since = datetime.now(pytz.utc)
    assert isinstance(await new_rel.save(), FriendRel)

    # start and end nodes are the opposite of what you'd expect when using either..
    # I've tried everything possible to correct this to no avail
    paul = await new_rel.start_node()
    tom = await new_rel.end_node()
    assert paul.name == "Tom"
    assert tom.name == "Paul"


@mark_async_test
async def test_direction_connect_with_rel_model():
    paul = await Badger(name="Paul the badger").save()
    ian = await Stoat(name="Ian the stoat").save()

    rel = await ian.hates.connect(
        paul, {"reason": "thinks paul should bath more often"}
    )
    assert isinstance(rel.since, datetime)
    assert isinstance(rel, FriendRel)
    assert rel.reason.startswith("thinks")
    rel.reason = "he smells"
    await rel.save()

    ian = await rel.start_node()
    assert isinstance(ian, Stoat)
    paul = await rel.end_node()
    assert isinstance(paul, Badger)

    assert ian.name.startswith("Ian")
    assert paul.name.startswith("Paul")

    rel = await ian.hates.relationship(paul)
    assert isinstance(rel, HatesRel)
    assert isinstance(rel.since, datetime)
    await rel.save()

    # test deflate checking
    rel.since = "2:30pm"
    with raises(DeflateError):
        await rel.save()

    # check deflate check via connect
    with raises(DeflateError):
        await paul.hates.connect(
            ian,
            {
                "reason": "thinks paul should bath more often",
                "since": "2:30pm",
            },
        )


@mark_async_test
async def test_traversal_where_clause():
    phill = await Badger(name="Phill the badger").save()
    tim = await Badger(name="Tim the badger").save()
    bob = await Badger(name="Bob the badger").save()
    rel = await tim.friend.connect(bob)
    now = datetime.now(pytz.utc)
    assert rel.since < now
    rel2 = await tim.friend.connect(phill)
    assert rel2.since > now
    friends = tim.friend.match(since__gt=now)
    assert len(await friends.all()) == 1


@mark_async_test
async def test_multiple_rels_exist_issue_223():
    # check a badger can dislike a stoat for multiple reasons
    phill = await Badger(name="Phill").save()
    ian = await Stoat(name="Stoat").save()

    rel_a = await phill.hates.connect(ian, {"reason": "a"})
    rel_b = await phill.hates.connect(ian, {"reason": "b"})
    assert rel_a.element_id != rel_b.element_id

    if AsyncUtil.is_async_code:
        ian_a = (await phill.hates.match(reason="a"))[0]
        ian_b = (await phill.hates.match(reason="b"))[0]
    else:
        ian_a = phill.hates.match(reason="a")[0]
        ian_b = phill.hates.match(reason="b")[0]
    assert ian_a.element_id == ian_b.element_id


@mark_async_test
async def test_retrieve_all_rels():
    tom = await Badger(name="tom").save()
    ian = await Stoat(name="ian").save()

    rel_a = await tom.hates.connect(ian, {"reason": "a"})
    rel_b = await tom.hates.connect(ian, {"reason": "b"})

    rels = await tom.hates.all_relationships(ian)
    assert len(rels) == 2
    assert rels[0].element_id in [rel_a.element_id, rel_b.element_id]
    assert rels[1].element_id in [rel_a.element_id, rel_b.element_id]


@mark_async_test
async def test_save_hook_on_rel_model():
    HOOKS_CALLED["pre_save"] = 0
    HOOKS_CALLED["post_save"] = 0

    paul = await Badger(name="PaulB").save()
    ian = await Stoat(name="IanS").save()

    rel = await ian.hates.connect(paul, {"reason": "yadda yadda"})
    await rel.save()

    assert HOOKS_CALLED["pre_save"] == 2
    assert HOOKS_CALLED["post_save"] == 2
