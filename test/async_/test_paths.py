from test._async_compat import mark_async_test

from neomodel import (
    AsyncNeomodelPath,
    AsyncRelationshipTo,
    AsyncStructuredNode,
    AsyncStructuredRel,
    IntegerProperty,
    StringProperty,
    UniqueIdProperty,
    adb,
)


class PersonLivesInCity(AsyncStructuredRel):
    """
    Relationship with data that will be instantiated as "stand-alone"
    """

    some_num = IntegerProperty(index=True, default=12)


class CountryOfOrigin(AsyncStructuredNode):
    code = StringProperty(unique_index=True, required=True)


class CityOfResidence(AsyncStructuredNode):
    name = StringProperty(required=True)
    country = AsyncRelationshipTo(CountryOfOrigin, "FROM_COUNTRY")


class PersonOfInterest(AsyncStructuredNode):
    uid = UniqueIdProperty()
    name = StringProperty(unique_index=True)
    age = IntegerProperty(index=True, default=0)

    country = AsyncRelationshipTo(CountryOfOrigin, "IS_FROM")
    city = AsyncRelationshipTo(CityOfResidence, "LIVES_IN", model=PersonLivesInCity)


@mark_async_test
async def test_path_instantiation():
    """
    Neo4j driver paths should be instantiated as neomodel paths, with all of
    their nodes and relationships resolved to their Python objects wherever
    such a mapping is available.
    """

    c1 = await CountryOfOrigin(code="GR").save()
    c2 = await CountryOfOrigin(code="FR").save()

    ct1 = await CityOfResidence(name="Athens", country=c1).save()
    ct2 = await CityOfResidence(name="Paris", country=c2).save()

    p1 = await PersonOfInterest(name="Bill", age=22).save()
    await p1.country.connect(c1)
    await p1.city.connect(ct1)

    p2 = await PersonOfInterest(name="Jean", age=28).save()
    await p2.country.connect(c2)
    await p2.city.connect(ct2)

    p3 = await PersonOfInterest(name="Bo", age=32).save()
    await p3.country.connect(c1)
    await p3.city.connect(ct2)

    p4 = await PersonOfInterest(name="Drop", age=16).save()
    await p4.country.connect(c1)
    await p4.city.connect(ct2)

    # Retrieve a single path
    q = await adb.cypher_query(
        "MATCH p=(:CityOfResidence{name:'Athens'})<-[:LIVES_IN]-(:PersonOfInterest)-[:IS_FROM]->(:CountryOfOrigin) RETURN p LIMIT 1",
        resolve_objects=True,
    )

    path_object = q[0][0][0]
    path_nodes = path_object.nodes
    path_rels = path_object.relationships

    assert isinstance(path_object, AsyncNeomodelPath)
    assert isinstance(path_nodes[0], CityOfResidence)
    assert isinstance(path_nodes[1], PersonOfInterest)
    assert isinstance(path_nodes[2], CountryOfOrigin)
    assert isinstance(path_object.start_node, CityOfResidence)
    assert isinstance(path_object.end_node, CountryOfOrigin)

    assert isinstance(path_rels[0], PersonLivesInCity)
    assert isinstance(path_rels[1], AsyncStructuredRel)

    path_string = str(path_object)
    assert path_string.startswith("<Path start=<CityOfResidence")
    assert path_string.endswith("size=2>")
    assert len(path_object) == 2
    for rel in path_object:
        assert isinstance(rel, AsyncStructuredRel)

    await c1.delete()
    await c2.delete()
    await ct1.delete()
    await ct2.delete()
    await p1.delete()
    await p2.delete()
    await p3.delete()
    await p4.delete()
