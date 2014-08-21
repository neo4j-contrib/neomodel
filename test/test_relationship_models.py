from neomodel import (StructuredNode, StructuredRel, Relationship, RelationshipTo,
        StringProperty, DateTimeProperty, DeflateError)
from datetime import datetime
import pytz


class FriendRel(StructuredRel):
    since = DateTimeProperty(default=lambda: datetime.now(pytz.utc))


class HatesRel(FriendRel):
    reason = StringProperty()


class Badger(StructuredNode):
    name = StringProperty(unique_index=True)
    friend = Relationship('Badger', 'FRIEND', model=FriendRel)
    hates = RelationshipTo('Stoat', 'HATES', model=HatesRel)


class Stoat(StructuredNode):
    name = StringProperty(unique_index=True)
    hates = RelationshipTo('Badger', 'HATES', model=HatesRel)


def test_either_connect_with_rel_model():
    paul = Badger(name="Paul").save()
    tom = Badger(name="Tom").save()

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
    assert paul.name == 'Paul'
    assert tom.name == 'Tom'


def test_direction_connect_with_rel_model():
    paul = Badger(name="Paul the badger").save()
    ian = Stoat(name="Ian the stoat").save()

    rel = ian.hates.connect(paul, {'reason': "thinks paul should bath more often"})
    assert isinstance(rel.since, datetime)
    assert isinstance(rel, FriendRel)
    assert rel.reason.startswith("thinks")
    rel.reason = 'he smells'
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
    try:
        rel.save()
    except DeflateError:
        assert True
    else:
        assert False

    # check deflate check via connect
    try:
        paul.hates.connect(ian, {'reason': "thinks paul should bath more often", 'since': '2:30pm'})
    except DeflateError:
        assert True
    else:
        assert False


def test_traversal_where_clause():
    phill = Badger(name="Phill the badger").save()
    tim = Badger(name="Tim the badger").save()
    bob = Badger(name="Bob the badger").save()
    rel = tim.friend.connect(bob)
    now = datetime.now(pytz.utc)
    assert rel.since < now
    rel2 = tim.friend.connect(phill)
    assert rel2.since > now
    friends = tim.friend.match(since__gt=now)
    assert len(friends) == 1
