import pytest
from test._async_compat import mark_sync_test
from neo4j.exceptions import ClientError
from pytest import raises

from neomodel.sync_.core import db
from neomodel.exceptions import FeatureNotSupported


@mark_sync_test
@pytest.mark.skipif(
    not db.edition_is_enterprise(), reason="Skipping test for community edition"
)
def test_impersonate():
    with db.impersonate(user="troygreene"):
        results, _ = db.cypher_query("RETURN 'Doo Wacko !'")
        assert results[0][0] == "Doo Wacko !"


@mark_sync_test
@pytest.mark.skipif(
    not db.edition_is_enterprise(), reason="Skipping test for community edition"
)
def test_impersonate_unauthorized():
    with db.impersonate(user="unknownuser"):
        with raises(ClientError):
            _ = db.cypher_query("RETURN 'Gabagool'")


@mark_sync_test
@pytest.mark.skipif(
    not db.edition_is_enterprise(), reason="Skipping test for community edition"
)
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


@mark_sync_test
@pytest.mark.skipif(
    db.edition_is_enterprise(), reason="Skipping test for enterprise edition"
)
def test_impersonate_community():
    with raises(FeatureNotSupported):
        with db.impersonate(user="troygreene"):
            _ = db.cypher_query("RETURN 'Gabagoogoo'")
