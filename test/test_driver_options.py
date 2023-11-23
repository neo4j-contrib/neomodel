import pytest
from neo4j.exceptions import ClientError
from pytest import raises

from neomodel._async.core import adb
from neomodel.exceptions import FeatureNotSupported


@pytest.mark.skipif(
    not adb.edition_is_enterprise(), reason="Skipping test for community edition"
)
def test_impersonate():
    with adb.impersonate(user="troygreene"):
        results, _ = adb.cypher_query_async("RETURN 'Doo Wacko !'")
        assert results[0][0] == "Doo Wacko !"


@pytest.mark.skipif(
    not adb.edition_is_enterprise(), reason="Skipping test for community edition"
)
def test_impersonate_unauthorized():
    with adb.impersonate(user="unknownuser"):
        with raises(ClientError):
            _ = adb.cypher_query_async("RETURN 'Gabagool'")


@pytest.mark.skipif(
    not adb.edition_is_enterprise(), reason="Skipping test for community edition"
)
def test_impersonate_multiple_transactions():
    with adb.impersonate(user="troygreene"):
        with adb.transaction:
            results, _ = adb.cypher_query_async("RETURN 'Doo Wacko !'")
            assert results[0][0] == "Doo Wacko !"

        with adb.transaction:
            results, _ = adb.cypher_query_async("SHOW CURRENT USER")
            assert results[0][0] == "troygreene"

    results, _ = adb.cypher_query_async("SHOW CURRENT USER")
    assert results[0][0] == "neo4j"


@pytest.mark.skipif(
    adb.edition_is_enterprise(), reason="Skipping test for enterprise edition"
)
def test_impersonate_community():
    with raises(FeatureNotSupported):
        with adb.impersonate(user="troygreene"):
            _ = adb.cypher_query_async("RETURN 'Gabagoogoo'")
