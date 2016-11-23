from neomodel import StructuredNode, StringProperty, db
from multiprocessing import Pool


class ThingyMaBob(StructuredNode):
    name = StringProperty(unique_index=True, required=True)


def thing_create(name):
    name = str(name)
    thing, = ThingyMaBob.get_or_create({'name': name})
    return thing.name, name


def test_concurrency():
    p = Pool(5)
    results = p.map(thing_create, range(50))
    for returned, sent in results:
        assert returned == sent
