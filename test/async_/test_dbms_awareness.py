from test._async_compat import mark_async_test

import pytest

from neomodel import adb
from neomodel.util import version_tag_to_integer


@mark_async_test
async def test_version_awareness():
    db_version = await adb.database_version
    if db_version != "5.7.0":
        pytest.skip("Testing a specific database version")
    assert db_version == "5.7.0"
    assert await adb.version_is_higher_than("5.7")
    assert await adb.version_is_higher_than("5.6.0")
    assert await adb.version_is_higher_than("5")
    assert await adb.version_is_higher_than("4")

    assert not await adb.version_is_higher_than("5.8")


@mark_async_test
async def test_edition_awareness():
    db_edition = await adb.database_edition
    if db_edition == "enterprise":
        assert await adb.edition_is_enterprise()
    else:
        assert not await adb.edition_is_enterprise()


def test_version_tag_to_integer():
    assert version_tag_to_integer("5.7.1") == 50701
    assert version_tag_to_integer("5.1") == 50100
    assert version_tag_to_integer("5") == 50000
    assert version_tag_to_integer("5.14.1") == 51401
    assert version_tag_to_integer("5.14-aura") == 51400
