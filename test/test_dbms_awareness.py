from pytest import mark

from neomodel._async.core import adb


@mark.skipif(
    adb.database_version != "5.7.0", reason="Testing a specific database version"
)
def test_version_awareness():
    assert adb.database_version == "5.7.0"
    assert adb.version_is_higher_than("5.7")
    assert adb.version_is_higher_than("5")
    assert adb.version_is_higher_than("4")

    assert not adb.version_is_higher_than("5.8")


def test_edition_awareness():
    if adb.database_edition == "enterprise":
        assert adb.edition_is_enterprise()
    else:
        assert not adb.edition_is_enterprise()
