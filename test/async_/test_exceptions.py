import pickle
from test._async_compat import mark_async_test

from neomodel import AsyncStructuredNode, DoesNotExist, StringProperty


class EPerson(AsyncStructuredNode):
    name = StringProperty(unique_index=True)


@mark_async_test
async def test_object_does_not_exist():
    try:
        await EPerson.nodes.get(name="johnny")
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
