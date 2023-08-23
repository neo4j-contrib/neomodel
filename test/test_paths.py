from neomodel import (StringProperty, StructuredNode, UniqueIdProperty, 
                      db, RelationshipTo, IntegerProperty, NeomodelPath, StructuredRel)

class PersonLivesInCity(StructuredRel):
    """
    Relationship with data that will be instantiated as "stand-alone"
    """
    some_num = IntegerProperty(index=True, default=12)

class CountryOfOrigin(StructuredNode):
    code = StringProperty(unique_index=True, required=True)

class CityOfResidence(StructuredNode):
    name = StringProperty(required=True)
    country = RelationshipTo(CountryOfOrigin, 'FROM_COUNTRY')

class PersonOfInterest(StructuredNode):
    uid = UniqueIdProperty()
    name = StringProperty(unique_index=True)
    age = IntegerProperty(index=True, default=0)

    country = RelationshipTo(CountryOfOrigin, 'IS_FROM')
    city = RelationshipTo(CityOfResidence, 'LIVES_IN', model=PersonLivesInCity)


def test_path_instantiation():
    """
    Neo4j driver paths should be instantiated as neomodel paths, with all of 
    their nodes and relationships resolved to their Python objects wherever 
    such a mapping is available.
    """

    c1=CountryOfOrigin(code="GR").save()
    c2=CountryOfOrigin(code="FR").save()

    ct1 = CityOfResidence(name="Athens", country = c1).save()
    ct2 = CityOfResidence(name="Paris", country = c2).save()


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
    q = db.cypher_query("MATCH p=(:CityOfResidence)<-[:LIVES_IN]-(:PersonOfInterest)-[:IS_FROM]->(:CountryOfOrigin) RETURN p LIMIT 1", resolve_objects = True)

    path_object = q[0][0][0]
    path_nodes = path_object.nodes
    path_rels = path_object.relationships

    assert type(path_object) is NeomodelPath
    assert type(path_nodes[0]) is CityOfResidence
    assert type(path_nodes[1]) is PersonOfInterest
    assert type(path_nodes[2]) is CountryOfOrigin

    assert type(path_rels[0]) is PersonLivesInCity
    assert type(path_rels[1]) is StructuredRel

    c1.delete()
    c2.delete()
    ct1.delete()
    ct2.delete()
    p1.delete()
    p2.delete()
    p3.delete()
    p4.delete()

