from test._async_compat import mark_async_test

import pytest
from neo4j.exceptions import ClientError
from pytest import raises

from neomodel import adb
from neomodel.exceptions import FeatureNotSupported


@mark_async_test
async def test_impersonate():
    if not await adb.edition_is_enterprise():
        pytest.skip("Skipping test for community edition")
    with await adb.impersonate(user="troygreene"):
        results, _ = await adb.cypher_query("RETURN 'Doo Wacko !'")
        assert results[0][0] == "Doo Wacko !"


@mark_async_test
async def test_impersonate_unauthorized():
    if not await adb.edition_is_enterprise():
        pytest.skip("Skipping test for community edition")
    with await adb.impersonate(user="unknownuser"):
        with raises(ClientError):
            _ = await adb.cypher_query("RETURN 'Gabagool'")


@mark_async_test
async def test_impersonate_multiple_transactions():
    if not await adb.edition_is_enterprise():
        pytest.skip("Skipping test for community edition")
    with await adb.impersonate(user="troygreene"):
        async with adb.transaction:
            results, _ = await adb.cypher_query("RETURN 'Doo Wacko !'")
            assert results[0][0] == "Doo Wacko !"

        async with adb.transaction:
            results, _ = await adb.cypher_query("SHOW CURRENT USER")
            assert results[0][0] == "troygreene"

    results, _ = await adb.cypher_query("SHOW CURRENT USER")
    assert results[0][0] == "neo4j"


@mark_async_test
async def test_impersonate_community():
    if await adb.edition_is_enterprise():
        pytest.skip("Skipping test for enterprise edition")
    with raises(FeatureNotSupported):
        with await adb.impersonate(user="troygreene"):
            _ = await adb.cypher_query("RETURN 'Gabagoogoo'")
