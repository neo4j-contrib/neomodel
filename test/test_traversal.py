from neomodel.traversal import Traversal, Query
from neomodel import (StructuredNode, RelationshipTo, StringProperty)


class Shopper(StructuredNode):
    name = StringProperty(unique_index=True)
    friend = RelationshipTo('Shopper', 'FRIEND')
    basket = RelationshipTo('Basket', 'BASKET')


class Basket(StructuredNode):
    item = RelationshipTo('ShoppingItem', 'ITEM')


class ShoppingItem(StructuredNode):
    name = StringProperty()


def setup_shopper(name, friend):
    jim = Shopper(name=name).save()
    bob = Shopper(name=friend).save()
    b = Basket().save()
    si1 = ShoppingItem(name='Tooth brush').save()
    si2 = ShoppingItem(name='Screwdriver').save()
    b.item.connect(si1)
    b.item.connect(si2)
    jim.friend.connect(bob)
    bob.basket.connect(b)
    return jim


def test_one_level_traversal():
    jim = setup_shopper('Jim', 'Bob')
    t = Traversal(jim)
    t.traverse('friend')
    results = t.execute()
    print Query(t.ast)
    from pprint import pprint as pp
    pp(results)
    assert t.ast[-1]['return'][0] is 'friend'
    assert t.ast[-3]['name'] == 'friend'


def test_multilevel_traversal():
    bill = setup_shopper('bill', 'ted')
    t = Traversal(bill)
    t.traverse('friend').traverse('basket')
    r = t.execute()
    print Query(t.ast)
    from pprint import pprint as pp
    pp(r)
