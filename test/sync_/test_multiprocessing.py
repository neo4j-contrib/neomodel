from multiprocessing.pool import ThreadPool as Pool
from test._async_compat import mark_sync_test

from neomodel import StringProperty, StructuredNode, db


class ThingyMaBob(StructuredNode):
    name = StringProperty(unique_index=True, required=True)


def thing_create(name):
    name = str(name)
    (thing,) = ThingyMaBob.get_or_create({"name": name})
    return thing.name, name


@mark_sync_test
def test_concurrency():
    with Pool(5) as p:
        results = p.map(thing_create, range(50))
        for to_unpack in results:
            returned, sent = to_unpack
            assert returned == sent
        db.close_connection()
