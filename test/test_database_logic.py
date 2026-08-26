"""
World-agnostic database-helper logic tests.

These exercise pure helpers from the database module (currently the
``_redact_params`` secret-masking used before query logging) without touching
the database or the async/sync split. They used to live in
``test/async_/test_database_management.py`` and were therefore transpiled and
run twice behind a live Neo4j session, even though the behaviour is identical
in both worlds and needs no connection.
"""

from neomodel.sync_.database import _redact_params


def test_redact_params_masks_password():
    """Sensitive parameter values must be masked before being logged."""
    assert _redact_params({"password": "supersecret", "user": "neo4j"}) == {
        "password": "******",
        "user": "neo4j",
    }
    # The real secret never appears in the redacted output.
    assert "supersecret" not in repr(_redact_params({"password": "supersecret"}))
    # Empty / missing params are passed through untouched.
    assert _redact_params(None) is None
    assert _redact_params({}) == {}


def test_redact_params_matches_sensitive_key_variants():
    """A range of secret-bearing key names should be masked, including
    compound and differently-cased variants."""
    # Use distinctive values that cannot appear as substrings of the (unredacted)
    # keys, so the leak check below is meaningful.
    sensitive = {
        "pwd": "secret-value-pwd",
        "Password": "secret-value-password",
        "user_password": "secret-value-user-password",
        "API_KEY": "secret-value-api-key",
        "stripe_api_key": "secret-value-stripe-api-key",
        "refresh_token": "secret-value-refresh-token",
        "client_secret": "secret-value-client-secret",
        "authorization": "secret-value-authorization",
        "otp": "secret-value-otp",
        "ssn": "secret-value-ssn",
    }
    redacted = _redact_params(sensitive)
    assert all(value == "******" for value in redacted.values()), redacted
    for original_value in sensitive.values():
        assert original_value not in repr(redacted)


def test_redact_params_does_not_over_redact():
    """Substring matching must not flag innocuous keys that merely contain a
    sensitive token as a fragment (e.g. 'author' contains 'auth')."""
    benign = {
        "author": "alice",
        "passenger": "bob",
        "monkey": "george",
        "user": "neo4j",
        "name": "thing",
    }
    assert _redact_params(benign) == benign
