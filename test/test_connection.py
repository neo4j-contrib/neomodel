import os

import pytest
from neo4j.debug import watch

from neomodel import config, db

INITIAL_URL = db.url


@pytest.fixture(autouse=True)
def setup_teardown():
    yield
    # Teardown actions after tests have run
    # Reconnect to initial URL for potential subsequent tests
    db.driver.close()
    db.set_connection(INITIAL_URL)


@pytest.fixture(autouse=True, scope="session")
def neo4j_logging():
    with watch("neo4j"):
        yield


@pytest.mark.parametrize("protocol", ["neo4j+s", "neo4j+ssc", "bolt+s", "bolt+ssc"])
def test_connect_to_aura(protocol):
    cypher_return = "hello world"
    default_cypher_query = f"RETURN '{cypher_return}'"
    db.driver.close()

    _set_connection(protocol=protocol)
    result, _ = db.cypher_query(default_cypher_query)

    assert len(result) > 0
    assert result[0][0] == cypher_return


def _set_connection(protocol):
    AURA_TEST_DB_USER = os.environ["AURA_TEST_DB_USER"]
    AURA_TEST_DB_PASSWORD = os.environ["AURA_TEST_DB_PASSWORD"]
    AURA_TEST_DB_HOSTNAME = os.environ["AURA_TEST_DB_HOSTNAME"]

    config.DATABASE_URL = f"{protocol}://{AURA_TEST_DB_USER}:{AURA_TEST_DB_PASSWORD}@{AURA_TEST_DB_HOSTNAME}"
    db.set_connection(config.DATABASE_URL)


@pytest.mark.parametrize(
    "url", ["bolt://user:password", "http://user:password@localhost:7687"]
)
def test_wrong_url_format(url):
    prev_url = db.url
    with pytest.raises(
        ValueError,
        match=rf"Expecting url format: bolt://user:password@localhost:7687 got {url}",
    ):
        db.set_connection(url)
