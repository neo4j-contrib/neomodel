from neomodel import (StructuredNode, Relationship, StringProperty)

class Meat(StructuredNode):
    name = StringProperty()

class Vegetable(StructuredNode):
    name = StringProperty()

class Refrigerator(StructuredNode):
    owner = StringProperty()
    contains = Relationship(['Meat', 'Vegetable'], 'CONTAINS')

def test_multi_connect():
    r = Refrigerator(owner='John').save()
    beef = Meat(name='beef').save()
    celery = Vegetable(name='celery').save()
    try:
        r.contains.connect(beef)
    except:
        assert False
    else:
        assert True
