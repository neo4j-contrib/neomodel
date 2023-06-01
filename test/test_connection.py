import os

import pytest
from neo4j.debug import watch

from neomodel import config, db


@pytest.mark.parametrize("protocol", ["neo4j+s", "neo4j+ssc", "bolt+s", "bolt+ssc"])
def test_connect_to_aura(protocol):
    watch("neo4j")
    cypher_return = "hello world"
    default_cypher_query = f"RETURN '{cypher_return}'"
    db.driver.close()

    _set_connection(protocol=protocol)
    result, _ = db.cypher_query(default_cypher_query)
    db.driver.close()

    assert len(result) > 0
    assert result[0][0] == cypher_return


def _set_connection(protocol):
    AURA_TEST_DB_USER = os.environ["AURA_TEST_DB_USER"]
    AURA_TEST_DB_PASSWORD = os.environ["AURA_TEST_DB_PASSWORD"]
    AURA_TEST_DB_HOSTNAME = os.environ["AURA_TEST_DB_HOSTNAME"]

    config.DATABASE_URL = f"{protocol}://{AURA_TEST_DB_USER}:{AURA_TEST_DB_PASSWORD}@{AURA_TEST_DB_HOSTNAME}"
    db.set_connection(config.DATABASE_URL)
