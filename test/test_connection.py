import os

from neomodel import config, db


def test_connect_to_aura():
    cypher_return = "hello world"
    default_cypher_query = f"RETURN '{cypher_return}'"
    db.driver.close()

    _set_connection(protocol="neo4j+s")
    neo4j_s_result, _ = db.cypher_query(default_cypher_query)
    db.driver.close()

    assert len(neo4j_s_result) > 0
    assert neo4j_s_result[0][0] == cypher_return

    _set_connection(protocol="neo4j+ssc")
    neo4j_ssc_result, _ = db.cypher_query(default_cypher_query)

    assert len(neo4j_ssc_result) > 0
    assert neo4j_ssc_result[0][0] == cypher_return
    db.driver.close()

    _set_connection(protocol="bolt+s")
    bolt_ssc_result, _ = db.cypher_query(default_cypher_query)

    assert len(bolt_ssc_result) > 0
    assert bolt_ssc_result[0][0] == cypher_return
    db.driver.close()

    _set_connection(protocol="bolt+ssc")
    bolt_ssc_result, _ = db.cypher_query(default_cypher_query)

    assert len(bolt_ssc_result) > 0
    assert bolt_ssc_result[0][0] == cypher_return
    db.driver.close()


def _set_connection(protocol, port=None):
    AURA_TEST_DB_USER = os.environ["AURA_TEST_DB_USER"]
    AURA_TEST_DB_PASSWORD = os.environ["AURA_TEST_DB_PASSWORD"]
    AURA_TEST_DB_HOSTNAME = os.environ["AURA_TEST_DB_HOSTNAME"]

    config.DATABASE_URL = f"{protocol}://{AURA_TEST_DB_USER}:{AURA_TEST_DB_PASSWORD}@{AURA_TEST_DB_HOSTNAME}"
    if port:
        config.DATABASE_URL += f":{port}"
    db.set_connection(config.DATABASE_URL)
