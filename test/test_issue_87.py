import neomodel
import py2neo
from neomodel import StructuredNode, StructuredRel, Relationship
from neomodel import StringProperty, DateTimeProperty, IntegerProperty
from datetime import datetime, timedelta
    
twelve_days = timedelta(days=12)
eleven_days = timedelta(days=11)
ten_days    = timedelta(days=10)
nine_days   = timedelta(days=9)
now         = datetime.now()

class FriendRelationship(StructuredRel):
    since = DateTimeProperty(default=datetime.now)
        
class Person(StructuredNode):
    name    = StringProperty()
    age     = IntegerProperty()
    friends = Relationship('Person','friend_of', model=FriendRelationship)
    

def setup_friends(person0, person1, since=None):
    rel = person0.friends.connect(person1)
    if (since):
        rel.since = since
        rel.save()
    return rel.since

def clear_db():
    db = py2neo.neo4j.GraphDatabaseService()
    db.clear()

def test_traversal_single_param():
    clear_db()
    jean  = Person(name="Jean", age=25).save()
    johan = Person(name="Johan", age=19).save()
    chris = Person(name="Chris", age=21).save()
    frank = Person(name="Frank", age=29).save()
    

    setup_friends(jean, johan, now - eleven_days)
    setup_friends(jean, chris, now - nine_days)
    setup_friends(chris, johan, now)
    setup_friends(chris, frank, now - nine_days)
     
    assert len(jean.traverse('friends', ('since','>', now - twelve_days)).run())   ==  2
    assert len(jean.traverse('friends', ('since','>', now - ten_days)).run())      ==  1
    assert len(jean.traverse('friends', ('since','>', now - nine_days)).run())     ==  0

def test_traversal_relationship_filter():
    clear_db()
    jean  = Person(name="Jean", age=25).save()
    johan = Person(name="Johan", age=19).save()
    chris = Person(name="Chris", age=21).save()
    frank = Person(name="Frank", age=29).save()
    
    setup_friends(jean, johan, now - eleven_days)
    setup_friends(jean, chris, now - nine_days)
    setup_friends(chris, johan, now)
    setup_friends(chris, frank, now - nine_days)
    
    assert len(jean.traverse('friends', ('since','>', now - twelve_days), ('since','<', now - ten_days)).run()) ==  1

def test_traversal_node_double_where():
    clear_db()
    jean  = Person(name="Jean", age=25).save()
    johan = Person(name="Johan", age=19).save()
    chris = Person(name="Chris", age=21).save()
    frank = Person(name="Frank", age=29).save()
    
    setup_friends(jean, johan, now - eleven_days)
    setup_friends(jean, chris, now - nine_days)
    setup_friends(chris, johan, now)
    setup_friends(chris, frank, now - nine_days)
    assert len(chris.traverse('friends').where('age','>', 18).where('age','<', 30).run()) ==  3
    assert len(chris.traverse('friends').where('age','>', 18).where('age','<', 29).run()) ==  2
