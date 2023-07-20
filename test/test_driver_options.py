from neo4j.exceptions import ClientError
from pytest import raises

from neomodel import db


@db.impersonate(user="troygreene")
def test_impersonate():
    results, _ = db.cypher_query("RETURN 'Doo Wacko !'")
    assert results[0][0] == "Doo Wacko !"


def test_impersonate_unauthorized():
    with db.impersonate(user="unknownuser"):
        with raises(ClientError):
            _ = db.cypher_query("RETURN 'Doo Wacko !'")


def test_impersonate_multiple_transactions():
    with db.impersonate(user="troygreene"):
        with db.transaction:
            results, _ = db.cypher_query("RETURN 'Doo Wacko !'")
            assert results[0][0] == "Doo Wacko !"

        with db.transaction:
            results, _ = db.cypher_query("SHOW CURRENT USER")
            assert results[0][0] == "troygreene"

    results, _ = db.cypher_query("SHOW CURRENT USER")
    assert results[0][0] == "neo4j"
