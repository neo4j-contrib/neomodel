from pytest import mark

from neomodel import db


@mark.skipif(
    db.database_version != "5.7.0", reason="Testing a specific database version"
)
def test_version_awareness():
    assert db.database_version == "5.7.0"
    assert db.version_is_higher_than("5.7")
    assert db.version_is_higher_than("5")
    assert db.version_is_higher_than("4")

    assert not db.version_is_higher_than("5.8")


def test_edition_awareness():
    if db.database_edition == "enterprise":
        assert db.edition_is_enterprise()
    else:
        assert not db.edition_is_enterprise()
