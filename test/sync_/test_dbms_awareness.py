from test._async_compat import mark_sync_test

import pytest

from neomodel import db
from neomodel.util import version_tag_to_integer


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


def test_version_tag_to_integer():
    assert version_tag_to_integer("5.7.1") == 50701
    assert version_tag_to_integer("5.1") == 50100
    assert version_tag_to_integer("5") == 50000
    assert version_tag_to_integer("5.14.1") == 51401
    assert version_tag_to_integer("5.14-aura") == 51400
