from neomodel import StructuredNode, StringProperty, IntegerProperty, UniqueProperty


class Human(StructuredNode):
    name = StringProperty(unique_index=True)
    age = IntegerProperty(index=True)


def test_unique_error():
    Human(name="j1m", age=13).save()
    try:
        Human(name="j1m", age=14).save()
    except UniqueProperty as e:
        assert True
        assert str(e).find('j1m')
        assert str(e).find('name')
        assert str(e).find('FooBarr')
    else:
        assert False


def test_optional_properties_dont_get_indexed():
    Human(name=None, age=99).save()
    h = Human.index.get(age=99)
    assert h
    assert h.name is None

    Human(age=98).save()
    h = Human.index.get(age=98)
    assert h
    assert h.name is None


def test_lucene_query():
    try:
        from lucenequerybuilder import Q
    except ImportError:
        return
    Human(name='sarah', age=3).save()
    Human(name='jim', age=4).save()
    Human(name='bob', age=5).save()
    Human(name='tim', age=2).save()
    names = [p.name for p in Human.index.search(Q('age', inrange=[3, 5]))]
    assert 'sarah' in names
    assert 'jim' in names
    assert 'bob' in names


def test_escaped_chars():
    Human(name='sarah:test', age=3).save()
    r = Human.index.search(name='sarah:test')
    assert r
    assert r[0].name == 'sarah:test'


def test_does_not_exist():
    try:
        Human.index.get(name='XXXX')
    except Human.DoesNotExist:
        assert True
    else:
        assert False


def test_index_inherited_props():

    class Mixin(object):
        extra = StringProperty(unique_index=True)

    class MixedHuman(Human, Mixin):
        pass

    jim = MixedHuman(age=23, name='jimmy', extra='extra').save()

    assert MixedHuman.index.name == 'MixedHuman'
    node = MixedHuman.index.get(extra='extra')
    assert node.name == jim.name
