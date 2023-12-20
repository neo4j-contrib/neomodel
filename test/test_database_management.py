import pytest
from neo4j.exceptions import AuthError

from neomodel import (
    AsyncStructuredNode,
    AsyncStructuredRel,
    IntegerProperty,
    RelationshipTo,
    StringProperty,
)
from neomodel._async.core import adb


class City(AsyncStructuredNode):
    name = StringProperty()


class InCity(AsyncStructuredRel):
    creation_year = IntegerProperty(index=True)


class Venue(AsyncStructuredNode):
    name = StringProperty(unique_index=True)
    creator = StringProperty(index=True)
    in_city = RelationshipTo(City, relation_type="IN", model=InCity)


def test_clear_database():
    venue = Venue(name="Royal Albert Hall", creator="Queen Victoria").save()
    city = City(name="London").save()
    venue.in_city.connect(city)

    # Clear only the data
    adb.clear_neo4j_database()
    database_is_populated, _ = adb.cypher_query(
        "MATCH (a) return count(a)>0 as database_is_populated"
    )

    assert database_is_populated[0][0] is False

    indexes = adb.list_indexes(exclude_token_lookup=True)
    constraints = adb.list_constraints()
    assert len(indexes) > 0
    assert len(constraints) > 0

    # Clear constraints and indexes too
    adb.clear_neo4j_database(clear_constraints=True, clear_indexes=True)

    indexes = adb.list_indexes(exclude_token_lookup=True)
    constraints = adb.list_constraints()
    assert len(indexes) == 0
    assert len(constraints) == 0


def test_change_password():
    prev_password = "foobarbaz"
    new_password = "newpassword"
    prev_url = f"bolt://neo4j:{prev_password}@localhost:7687"
    new_url = f"bolt://neo4j:{new_password}@localhost:7687"

    adb.change_neo4j_password("neo4j", new_password)
    adb.close_connection()

    adb.set_connection(url=new_url)
    adb.close_connection()

    with pytest.raises(AuthError):
        adb.set_connection(url=prev_url)

    adb.close_connection()

    adb.set_connection(url=new_url)
    adb.change_neo4j_password("neo4j", prev_password)
    adb.close_connection()

    adb.set_connection(url=prev_url)
