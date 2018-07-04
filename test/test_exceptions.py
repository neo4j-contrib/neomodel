import pickle

from neomodel import StructuredNode, StringProperty, DoesNotExist


class Person(StructuredNode):
    name = StringProperty(unique_index=True)


def test_object_does_not_exist():
    try:
        Person.nodes.get(name="johnny")
    except Person.DoesNotExist as e:
        pickle_instance = pickle.dumps(e)
        assert pickle_instance
        assert pickle.loads(pickle_instance)
        assert isinstance(pickle.loads(pickle_instance), DoesNotExist)
    else:
        assert False, "Person.DoesNotExist not raised."


def test_pickle_does_not_exist():
    try:
        raise Person.DoesNotExist("My Test Message")
    except Person.DoesNotExist as e:
        pickle_instance = pickle.dumps(e)
        assert pickle_instance
        assert pickle.loads(pickle_instance)
        assert isinstance(pickle.loads(pickle_instance), DoesNotExist)
