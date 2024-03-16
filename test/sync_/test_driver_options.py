from test._async_compat import mark_sync_test

import pytest
from neo4j.exceptions import ClientError
from pytest import raises

from neomodel import db
from neomodel.exceptions import FeatureNotSupported


@mark_sync_test
def test_impersonate():
    if not db.edition_is_enterprise():
        pytest.skip("Skipping test for community edition")
    with db.impersonate(user="troygreene"):
        results, _ = db.cypher_query("RETURN 'Doo Wacko !'")
        assert results[0][0] == "Doo Wacko !"


@mark_sync_test
def test_impersonate_unauthorized():
    if not db.edition_is_enterprise():
        pytest.skip("Skipping test for community edition")
    with db.impersonate(user="unknownuser"):
        with raises(ClientError):
            _ = db.cypher_query("RETURN 'Gabagool'")


@mark_sync_test
def test_impersonate_multiple_transactions():
    if not db.edition_is_enterprise():
        pytest.skip("Skipping test for community edition")
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
def test_impersonate_community():
    if db.edition_is_enterprise():
        pytest.skip("Skipping test for enterprise edition")
    with raises(FeatureNotSupported):
        with db.impersonate(user="troygreene"):
            _ = db.cypher_query("RETURN 'Gabagoogoo'")
