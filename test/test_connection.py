import os

import pytest
from neo4j import GraphDatabase
from neo4j.debug import watch

from neomodel import StringProperty, StructuredNode, config, db

from .conftest import NEO4J_PASSWORD, NEO4J_URL, NEO4J_USERNAME


@pytest.fixture(autouse=True)
def setup_teardown():
    yield
    # Teardown actions after tests have run
    # Reconnect to initial URL for potential subsequent tests
    db.close_connection()
    db.set_connection(url=config.DATABASE_URL)


@pytest.fixture(autouse=True, scope="session")
def neo4j_logging():
    with watch("neo4j"):
        yield


class Pastry(StructuredNode):
    name = StringProperty(unique_index=True)


def test_set_connection_driver_works():
    # Verify that current connection is up
    assert Pastry(name="Chocolatine").save()
    db.close_connection()

    # Test connection using a driver
    db.set_connection(
        driver=GraphDatabase().driver(NEO4J_URL, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
    )
    assert Pastry(name="Croissant").save()


@pytest.mark.parametrize(
    "url", ["bolt://user:password", "http://user:password@localhost:7687"]
)
def test_wrong_url_format(url):
    with pytest.raises(
        ValueError,
        match=rf"Expecting url format: bolt://user:password@localhost:7687 got {url}",
    ):
        db.set_connection(url=url)


@pytest.mark.parametrize("protocol", ["neo4j+s", "neo4j+ssc", "bolt+s", "bolt+ssc"])
def test_connect_to_aura(protocol):
    cypher_return = "hello world"
    default_cypher_query = f"RETURN '{cypher_return}'"
    db.close_connection()

    _set_connection(protocol=protocol)
    result, _ = db.cypher_query(default_cypher_query)

    assert len(result) > 0
    assert result[0][0] == cypher_return


def _set_connection(protocol):
    AURA_TEST_DB_USER = os.environ["AURA_TEST_DB_USER"]
    AURA_TEST_DB_PASSWORD = os.environ["AURA_TEST_DB_PASSWORD"]
    AURA_TEST_DB_HOSTNAME = os.environ["AURA_TEST_DB_HOSTNAME"]

    database_url = f"{protocol}://{AURA_TEST_DB_USER}:{AURA_TEST_DB_PASSWORD}@{AURA_TEST_DB_HOSTNAME}"
    db.set_connection(url=database_url)
