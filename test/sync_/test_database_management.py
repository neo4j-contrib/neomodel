from test._async_compat import mark_sync_test

import pytest
from neo4j.exceptions import AuthError

from neomodel import (
    IntegerProperty,
    RelationshipTo,
    StringProperty,
    StructuredNode,
    StructuredRel,
    db,
)


class City(StructuredNode):
    name = StringProperty()


class InCity(StructuredRel):
    creation_year = IntegerProperty(index=True)


class Venue(StructuredNode):
    name = StringProperty(unique_index=True)
    creator = StringProperty(index=True)
    in_city = RelationshipTo(City, relation_type="IN", model=InCity)


@mark_sync_test
def test_clear_database():
    venue = Venue(name="Royal Albert Hall", creator="Queen Victoria").save()
    city = City(name="London").save()
    venue.in_city.connect(city)

    # Clear only the data
    db.clear_neo4j_database()
    database_is_populated, _ = db.cypher_query(
        "MATCH (a) return count(a)>0 as database_is_populated"
    )

    assert database_is_populated[0][0] is False

    db.install_all_labels()
    indexes = db.list_indexes(exclude_token_lookup=True)
    constraints = db.list_constraints()
    assert len(indexes) > 0
    assert len(constraints) > 0

    # Clear constraints and indexes too
    db.clear_neo4j_database(clear_constraints=True, clear_indexes=True)

    indexes = db.list_indexes(exclude_token_lookup=True)
    constraints = db.list_constraints()
    assert len(indexes) == 0
    assert len(constraints) == 0


@mark_sync_test
def test_change_password():
    prev_password = "foobarbaz"
    new_password = "newpassword"
    prev_url = f"bolt://neo4j:{prev_password}@localhost:7687"
    new_url = f"bolt://neo4j:{new_password}@localhost:7687"

    db.change_neo4j_password("neo4j", new_password)
    db.close_connection()

    db.set_connection(url=new_url)
    db.close_connection()

    with pytest.raises(AuthError):
        db.set_connection(url=prev_url)

    db.close_connection()

    db.set_connection(url=new_url)
    db.change_neo4j_password("neo4j", prev_password)
    db.close_connection()

    db.set_connection(url=prev_url)
