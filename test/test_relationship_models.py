from neomodel import (StructuredNode, StructuredRel, Relationship, StringProperty, DateTimeProperty)
from datetime import datetime
import pytz


class FriendRel(StructuredRel):
    since = DateTimeProperty(default=lambda: datetime.now(pytz.utc))


class Badger(StructuredNode):
    name = StringProperty(unique_index=True)
    friend = Relationship('Badger', 'FRIEND', model=FriendRel)


def test_rel_model():
    paul = Badger(name="Paul").save()
    tom = Badger(name="Tom").save()
    new_rel = paul.friend.connect(tom)
    from pprint import pprint as pp
    pp(new_rel.since)
    assert isinstance(new_rel, FriendRel)
    paul.traverse('friend').rels()
