from test._async_compat import mark_sync_test

import pytest

from neomodel import db


@mark_sync_test
def test_version_awareness():
    db_version = db.database_version
    if db_version != "5.7.0":
        pytest.skip("Testing a specific database version")
    assert db_version == "5.7.0"
    assert db.version_is_higher_than("5.7")
    assert db.version_is_higher_than("5.6.0")
    assert db.version_is_higher_than("5")
    assert db.version_is_higher_than("4")

    assert not db.version_is_higher_than("5.8")


@mark_sync_test
def test_edition_awareness():
    db_edition = db.database_edition
    if db_edition == "enterprise":
        assert db.edition_is_enterprise()
    else:
        assert not db.edition_is_enterprise()
