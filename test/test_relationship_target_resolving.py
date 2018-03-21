from neomodel import StructuredNode, RelationshipTo, StringProperty

from test.test_relationships import Person


class Pet(StructuredNode):
    __abstract_node__ = True
    name = StringProperty()


class Cat(Pet):
    fed_by = RelationshipTo('.test_relationships.Person', 'FED_BY')


class Dog(Pet):
    walked_by = RelationshipTo('test.test_relationships.Person', 'WALKED_BY')


def test_query_without_initialized_node():
    Dog.nodes.all()


def test_absolute_relationship():
    dog = Dog(name='Snoopy').save()
    owner = Person(name='Charlie Brown').save()
    dog.walked_by.connect(owner)
    assert dog.walked_by.is_connected(owner)


def test_relative_relationship():
    cat = Cat(name='snufkin').save()
    owner = Person(name='Jon Arbuckle').save()
    cat.fed_by.connect(owner)
    assert cat.fed_by.is_connected(owner)
