from test._async_compat import mark_async_test

import pytest
from neo4j.exceptions import ClientError
from pytest import raises

from neomodel.async_.core import adb
from neomodel.exceptions import FeatureNotSupported


@mark_async_test
@pytest.mark.skipif(
    not adb.edition_is_enterprise(), reason="Skipping test for community edition"
)
async def test_impersonate():
    with adb.impersonate(user="troygreene"):
        results, _ = await adb.cypher_query("RETURN 'Doo Wacko !'")
        assert results[0][0] == "Doo Wacko !"


@mark_async_test
@pytest.mark.skipif(
    not adb.edition_is_enterprise(), reason="Skipping test for community edition"
)
async def test_impersonate_unauthorized():
    with adb.impersonate(user="unknownuser"):
        with raises(ClientError):
            _ = await adb.cypher_query("RETURN 'Gabagool'")


@mark_async_test
@pytest.mark.skipif(
    not adb.edition_is_enterprise(), reason="Skipping test for community edition"
)
async def test_impersonate_multiple_transactions():
    with adb.impersonate(user="troygreene"):
        with adb.transaction:
            results, _ = await adb.cypher_query("RETURN 'Doo Wacko !'")
            assert results[0][0] == "Doo Wacko !"

        with adb.transaction:
            results, _ = await adb.cypher_query("SHOW CURRENT USER")
            assert results[0][0] == "troygreene"

    results, _ = await adb.cypher_query("SHOW CURRENT USER")
    assert results[0][0] == "neo4j"


@mark_async_test
@pytest.mark.skipif(
    adb.edition_is_enterprise(), reason="Skipping test for enterprise edition"
)
async def test_impersonate_community():
    with raises(FeatureNotSupported):
        with adb.impersonate(user="troygreene"):
            _ = await adb.cypher_query("RETURN 'Gabagoogoo'")
