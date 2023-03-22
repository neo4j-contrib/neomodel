import pickle

from neomodel import DoesNotExist, StringProperty, StructuredNode


class EPerson(StructuredNode):
    name = StringProperty(unique_index=True)


def test_object_does_not_exist():
    try:
        EPerson.nodes.get(name="johnny")
    except EPerson.DoesNotExist as e:
        pickle_instance = pickle.dumps(e)
        assert pickle_instance
        assert pickle.loads(pickle_instance)
        assert isinstance(pickle.loads(pickle_instance), DoesNotExist)
    else:
        assert False, "Person.DoesNotExist not raised."


def test_pickle_does_not_exist():
    try:
        raise EPerson.DoesNotExist("My Test Message")
    except EPerson.DoesNotExist as e:
        pickle_instance = pickle.dumps(e)
        assert pickle_instance
        assert pickle.loads(pickle_instance)
        assert isinstance(pickle.loads(pickle_instance), DoesNotExist)
