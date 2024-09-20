from test._async_compat import mark_sync_test

from neomodel import (
    IntegerProperty,
    NeomodelPath,
    RelationshipTo,
    StringProperty,
    StructuredNode,
    StructuredRel,
    UniqueIdProperty,
    db,
)


class PersonLivesInCity(StructuredRel):
    """
    Relationship with data that will be instantiated as "stand-alone"
    """

    some_num = IntegerProperty(index=True, default=12)


class CountryOfOrigin(StructuredNode):
    code = StringProperty(unique_index=True, required=True)


class CityOfResidence(StructuredNode):
    name = StringProperty(required=True)
    country = RelationshipTo(CountryOfOrigin, "FROM_COUNTRY")


class PersonOfInterest(StructuredNode):
    uid = UniqueIdProperty()
    name = StringProperty(unique_index=True)
    age = IntegerProperty(index=True, default=0)

    country = RelationshipTo(CountryOfOrigin, "IS_FROM")
    city = RelationshipTo(CityOfResidence, "LIVES_IN", model=PersonLivesInCity)


@mark_sync_test
def test_path_instantiation():
    """
    Neo4j driver paths should be instantiated as neomodel paths, with all of
    their nodes and relationships resolved to their Python objects wherever
    such a mapping is available.
    """

    c1 = CountryOfOrigin(code="GR").save()
    c2 = CountryOfOrigin(code="FR").save()

    ct1 = CityOfResidence(name="Athens", country=c1).save()
    ct2 = CityOfResidence(name="Paris", country=c2).save()

    p1 = PersonOfInterest(name="Bill", age=22).save()
    p1.country.connect(c1)
    p1.city.connect(ct1)

    p2 = PersonOfInterest(name="Jean", age=28).save()
    p2.country.connect(c2)
    p2.city.connect(ct2)

    p3 = PersonOfInterest(name="Bo", age=32).save()
    p3.country.connect(c1)
    p3.city.connect(ct2)

    p4 = PersonOfInterest(name="Drop", age=16).save()
    p4.country.connect(c1)
    p4.city.connect(ct2)

    # Retrieve a single path
    q = db.cypher_query(
        "MATCH p=(:CityOfResidence{name:'Athens'})<-[:LIVES_IN]-(:PersonOfInterest)-[:IS_FROM]->(:CountryOfOrigin) RETURN p LIMIT 1",
        resolve_objects=True,
    )

    path_object = q[0][0][0]
    path_nodes = path_object.nodes
    path_rels = path_object.relationships

    assert isinstance(path_object, NeomodelPath)
    assert isinstance(path_nodes[0], CityOfResidence)
    assert isinstance(path_nodes[1], PersonOfInterest)
    assert isinstance(path_nodes[2], CountryOfOrigin)
    assert isinstance(path_object.start_node, CityOfResidence)
    assert isinstance(path_object.end_node, CountryOfOrigin)

    assert isinstance(path_rels[0], PersonLivesInCity)
    assert isinstance(path_rels[1], StructuredRel)

    path_string = str(path_object)
    assert path_string.startswith("<Path start=<CityOfResidence")
    assert path_string.endswith("size=2>")
    assert len(path_object) == 2
    for rel in path_object:
        assert isinstance(rel, StructuredRel)

    c1.delete()
    c2.delete()
    ct1.delete()
    ct2.delete()
    p1.delete()
    p2.delete()
    p3.delete()
    p4.delete()
