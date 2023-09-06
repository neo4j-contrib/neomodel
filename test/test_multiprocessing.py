from multiprocessing.pool import ThreadPool as Pool

from neomodel import StringProperty, StructuredNode, db


class ThingyMaBob(StructuredNode):
    name = StringProperty(unique_index=True, required=True)


def thing_create(name):
    name = str(name)
    (thing,) = ThingyMaBob.get_or_create({"name": name})
    return thing.name, name


def test_concurrency():
    with Pool(5) as p:
        results = p.map(thing_create, range(50))
        for returned, sent in results:
            assert returned == sent
        db.close_connection()
