from neomodel.traversal import TraversalSet
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
    t = TraversalSet(jim)
    t.traverse('friend')
    ast = t._finalise()
    results = t._execute_and_inflate(ast)
    assert ast[-1]['return'][0] is 'friend'
    assert ast[-3]['name'] == 'friend'
    assert results[0].__class__ is Shopper


def test_multilevel_traversal():
    bill = setup_shopper('bill', 'ted')
    result = bill.traverse('friend').traverse('basket').traverse('item')
    for i in result:
        assert i.__class__ is ShoppingItem
    assert 'Screwdriver' in [i.name for i in result]


def test_none_existant_relmanager():
    t = Shopper(name='Test').save()
    try:
        t.traverse('friend').traverse('foo')
    except AttributeError:
        assert True
    else:
        assert False


def test_iteration():
    jim = setup_shopper('Jill', 'Barbra')
    jim.friend.connect(Shopper(name='timothy').save())
    for item in jim.traverse('friend'):
        assert item.__class__.__name__ is 'Shopper'


def test_len_and_bool():
    jim = setup_shopper('Jill1', 'Barbra2')
    assert len(jim.traverse('friend'))


def test_slice_and_index():
    jim = setup_shopper('Jill2', 'Barbra3')
    for i in jim.traverse('friend')[0:3]:
        assert i
    print jim.traverse('friend')[2]
