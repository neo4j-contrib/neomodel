from pytest import mark
from test._async_compat import mark_async_test

from neomodel.async_.core import adb
from neomodel.util import version_tag_to_integer


@mark.skipif(
    adb.database_version != "5.7.0", reason="Testing a specific database version"
)
async def test_version_awareness():
    assert adb.database_version == "5.7.0"
    assert adb.version_is_higher_than("5.7")
    assert adb.version_is_higher_than("5.6.0")
    assert adb.version_is_higher_than("5")
    assert adb.version_is_higher_than("4")

    assert not adb.version_is_higher_than("5.8")


@mark_async_test
async def test_edition_awareness():
    if adb.database_edition == "enterprise":
        assert await adb.edition_is_enterprise()
    else:
        assert not await adb.edition_is_enterprise()


def test_version_tag_to_integer():
    assert version_tag_to_integer("5.7.1") == 50701
    assert version_tag_to_integer("5.1") == 50100
    assert version_tag_to_integer("5") == 50000
    assert version_tag_to_integer("5.14.1") == 51401
    assert version_tag_to_integer("5.14-aura") == 51400
