from datetime import datetime

import pytz
from pytest import raises

from neomodel import (
    DateTimeProperty,
    DeflateError,
    Relationship,
    RelationshipTo,
    StringProperty,
    StructuredNodeAsync,
    StructuredRel,
)

HOOKS_CALLED = {"pre_save": 0, "post_save": 0}


class FriendRel(StructuredRel):
    since = DateTimeProperty(default=lambda: datetime.now(pytz.utc))


class HatesRel(FriendRel):
    reason = StringProperty()

    def pre_save(self):
        HOOKS_CALLED["pre_save"] += 1

    def post_save(self):
        HOOKS_CALLED["post_save"] += 1


class Badger(StructuredNodeAsync):
    name = StringProperty(unique_index=True)
    friend = Relationship("Badger", "FRIEND", model=FriendRel)
    hates = RelationshipTo("Stoat", "HATES", model=HatesRel)


class Stoat(StructuredNodeAsync):
    name = StringProperty(unique_index=True)
    hates = RelationshipTo("Badger", "HATES", model=HatesRel)


def test_either_connect_with_rel_model():
    paul = Badger(name="Paul").save_async()
    tom = Badger(name="Tom").save_async()

    # creating rels
    new_rel = tom.friend.disconnect(paul)
    new_rel = tom.friend.connect(paul)
    assert isinstance(new_rel, FriendRel)
    assert isinstance(new_rel.since, datetime)

    # updating properties
    new_rel.since = datetime.now(pytz.utc)
    assert isinstance(new_rel.save(), FriendRel)

    # start and end nodes are the opposite of what you'd expect when using either..
    # I've tried everything possible to correct this to no avail
    paul = new_rel.start_node()
    tom = new_rel.end_node()
    assert paul.name == "Tom"
    assert tom.name == "Paul"


def test_direction_connect_with_rel_model():
    paul = Badger(name="Paul the badger").save_async()
    ian = Stoat(name="Ian the stoat").save_async()

    rel = ian.hates.connect(paul, {"reason": "thinks paul should bath more often"})
    assert isinstance(rel.since, datetime)
    assert isinstance(rel, FriendRel)
    assert rel.reason.startswith("thinks")
    rel.reason = "he smells"
    rel.save()

    ian = rel.start_node()
    assert isinstance(ian, Stoat)
    paul = rel.end_node()
    assert isinstance(paul, Badger)

    assert ian.name.startswith("Ian")
    assert paul.name.startswith("Paul")

    rel = ian.hates.relationship(paul)
    assert isinstance(rel, HatesRel)
    assert isinstance(rel.since, datetime)
    rel.save()

    # test deflate checking
    rel.since = "2:30pm"
    with raises(DeflateError):
        rel.save()

    # check deflate check via connect
    with raises(DeflateError):
        paul.hates.connect(
            ian,
            {
                "reason": "thinks paul should bath more often",
                "since": "2:30pm",
            },
        )


def test_traversal_where_clause():
    phill = Badger(name="Phill the badger").save_async()
    tim = Badger(name="Tim the badger").save_async()
    bob = Badger(name="Bob the badger").save_async()
    rel = tim.friend.connect(bob)
    now = datetime.now(pytz.utc)
    assert rel.since < now
    rel2 = tim.friend.connect(phill)
    assert rel2.since > now
    friends = tim.friend.match(since__gt=now)
    assert len(friends) == 1


def test_multiple_rels_exist_issue_223():
    # check a badger can dislike a stoat for multiple reasons
    phill = Badger(name="Phill").save_async()
    ian = Stoat(name="Stoat").save_async()

    rel_a = phill.hates.connect(ian, {"reason": "a"})
    rel_b = phill.hates.connect(ian, {"reason": "b"})
    assert rel_a.element_id != rel_b.element_id

    ian_a = phill.hates.match(reason="a")[0]
    ian_b = phill.hates.match(reason="b")[0]
    assert ian_a.element_id == ian_b.element_id


def test_retrieve_all_rels():
    tom = Badger(name="tom").save_async()
    ian = Stoat(name="ian").save_async()

    rel_a = tom.hates.connect(ian, {"reason": "a"})
    rel_b = tom.hates.connect(ian, {"reason": "b"})

    rels = tom.hates.all_relationships(ian)
    assert len(rels) == 2
    assert rels[0].element_id in [rel_a.element_id, rel_b.element_id]
    assert rels[1].element_id in [rel_a.element_id, rel_b.element_id]


def test_save_hook_on_rel_model():
    HOOKS_CALLED["pre_save"] = 0
    HOOKS_CALLED["post_save"] = 0

    paul = Badger(name="PaulB").save_async()
    ian = Stoat(name="IanS").save_async()

    rel = ian.hates.connect(paul, {"reason": "yadda yadda"})
    rel.save()

    assert HOOKS_CALLED["pre_save"] == 2
    assert HOOKS_CALLED["post_save"] == 2
