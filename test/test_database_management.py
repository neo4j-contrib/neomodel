import pytest
from neo4j.exceptions import AuthError

from neomodel import (
    IntegerProperty,
    RelationshipTo,
    StringProperty,
    StructuredNode,
    StructuredRel,
    db,
    util,
)


class City(StructuredNode):
    name = StringProperty()


class InCity(StructuredRel):
    creation_year = IntegerProperty(index=True)


class Venue(StructuredNode):
    name = StringProperty(unique_index=True)
    creator = StringProperty(index=True)
    in_city = RelationshipTo(City, relation_type="IN", model=InCity)


def test_clear_database():
    venue = Venue(name="Royal Albert Hall", creator="Queen Victoria").save()
    city = City(name="London").save()
    venue.in_city.connect(city)

    # Clear only the data
    util.clear_neo4j_database(db)
    database_is_populated, _ = db.cypher_query(
        "MATCH (a) return count(a)>0 as database_is_populated"
    )

    assert database_is_populated[0][0] is False

    indexes = db.list_indexes(exclude_token_lookup=True)
    constraints = db.list_constraints()
    assert len(indexes) > 0
    assert len(constraints) > 0

    # Clear constraints and indexes too
    util.clear_neo4j_database(db, clear_constraints=True, clear_indexes=True)

    indexes = db.list_indexes(exclude_token_lookup=True)
    constraints = db.list_constraints()
    assert len(indexes) == 0
    assert len(constraints) == 0


def test_change_password():
    prev_password = "foobarbaz"
    new_password = "newpassword"
    prev_url = f"bolt://neo4j:{prev_password}@localhost:7687"
    new_url = f"bolt://neo4j:{new_password}@localhost:7687"

    util.change_neo4j_password(db, "neo4j", new_password)
    db.close_connection()

    db.set_connection(url=new_url)
    db.close_connection()

    with pytest.raises(AuthError):
        db.set_connection(url=prev_url)

    db.close_connection()

    db.set_connection(url=new_url)
    util.change_neo4j_password(db, "neo4j", prev_password)
    db.close_connection()

    db.set_connection(url=prev_url)
