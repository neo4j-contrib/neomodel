import os

from neomodel import config, db


def test_connect_to_aura():
    cypher_return = "hello world"
    default_cypher_query = f"RETURN '{cypher_return}'"

    _set_connection(protocol="neo4j+ssc")
    result, _ = db.cypher_query(default_cypher_query)

    assert len(result) > 0
    assert result[0][0] == cypher_return

    _set_connection(protocol="bolt+ssc")
    result, _ = db.cypher_query(default_cypher_query)

    assert len(result) > 0
    assert result[0][0] == cypher_return


def _set_connection(protocol, port=None):
    AURA_TEST_DB_USER = os.environ["AURA_TEST_DB_USER"]
    AURA_TEST_DB_PASSWORD = os.environ["AURA_TEST_DB_PASSWORD"]
    AURA_TEST_DB_HOSTNAME = os.environ["AURA_TEST_DB_HOSTNAME"]

    config.DATABASE_URL = f"{protocol}://{AURA_TEST_DB_USER}:{AURA_TEST_DB_PASSWORD}@{AURA_TEST_DB_HOSTNAME}"
    if port:
        config.DATABASE_URL += f":{port}"
    db.set_connection(config.DATABASE_URL)
