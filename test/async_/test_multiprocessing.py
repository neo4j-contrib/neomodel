from multiprocessing.pool import ThreadPool as Pool
from test._async_compat import mark_async_test

from neomodel import AsyncStructuredNode, StringProperty, adb


class ThingyMaBob(AsyncStructuredNode):
    name = StringProperty(unique_index=True, required=True)


async def thing_create(name):
    name = str(name)
    (thing,) = await ThingyMaBob.get_or_create({"name": name})
    return thing.name, name


@mark_async_test
async def test_concurrency():
    with Pool(5) as p:
        results = p.map(thing_create, range(50))
        for to_unpack in results:
            returned, sent = await to_unpack
            assert returned == sent
        await adb.close_connection()
