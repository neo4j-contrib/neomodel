from neomodel.traversal import TraversalSet
from neomodel import (StructuredNode, RelationshipTo, StringProperty)


class Shopper(StructuredNode):
    name = StringProperty(unique_index=True)
    friend = RelationshipTo('Shopper', 'FRIEND')
    basket = RelationshipTo('Basket', 'BASKET')


class ShoppingItem(StructuredNode):
    name = StringProperty()


class Basket(StructuredNode):
    item = RelationshipTo([ShoppingItem], 'ITEM')


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
    for friend in t.traverse('friend'):
        assert isinstance(friend, Shopper)
    assert t.last_ast[-1]['return'][0] == 'friend'
    assert t.last_ast[-3]['name'] == 'friend'


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
    i = 0
    for item in jim.traverse('friend'):
        i += 1
        assert isinstance(item, (Shopper,))
    assert i


def test_len_and_bool():
    jim = setup_shopper('Jill1', 'Barbra2')
    assert len(jim.traverse('friend'))


def test_slice_and_index():
    jim = setup_shopper('Jill2', 'Barbra3')
    jim.friend.connect(Shopper(name='Fred').save())
    jim.friend.connect(Shopper(name='Terry').save())
    for i in jim.traverse('friend').limit(3):
        assert isinstance(i, Shopper)
    assert isinstance(jim.traverse('friend').run()[1], Shopper)


def test_order_by_skip_limit():
    zara = Shopper(name='Zara').save()
    zara.friend.connect(Shopper(name='Alan').save())
    zara.friend.connect(Shopper(name='Wendy').save())
    friends = zara.traverse('friend').order_by('friend.name').limit(2).run()
    assert friends[0].name == 'Alan'
    assert friends[1].name == 'Wendy'
    friends = zara.traverse('friend').order_by_desc('name').skip(1).limit(1).run()
    assert friends[0].name == 'Alan'
    friends = zara.traverse('friend').order_by_desc('name').skip(1).limit(1).run()
    assert friends[0].name == 'Alan'


def test_where_clause():
    terrance = setup_shopper('Terrance', 'Teriesa')
    results = terrance.traverse('friend').where('name', '=', 'Teriesa').where('age?', '>', 7).limit(1).run()
    assert results[0].name == 'Teriesa'
