import builtins
from test._async_compat import mark_sync_test
from unittest.mock import Mock, patch

import pytest
from neo4j.exceptions import ClientError
from neo4j.exceptions import ClientError as CypherError
from neo4j.exceptions import SessionExpired

from neomodel import StringProperty, StructuredNode, db
from neomodel._async_compat.util import Lock, Util
from neomodel.config import get_config
from neomodel.exceptions import ConstraintValidationFailed, UniqueProperty
from neomodel.sync_.database import Database
from neomodel.sync_.query import QueryRunner


class User2(StructuredNode):
    name = StringProperty()
    email = StringProperty()


class UserPandas(StructuredNode):
    name = StringProperty()
    email = StringProperty()


class UserNP(StructuredNode):
    name = StringProperty()
    email = StringProperty()


@pytest.fixture
def hide_available_pkg(monkeypatch, request):
    import_orig = builtins.__import__

    def mocked_import(name, *args, **kwargs):
        if name == request.param:
            raise ImportError()
        return import_orig(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mocked_import)


@mark_sync_test
def test_cypher():
    """
    test result format is backward compatible with earlier versions of neomodel
    """

    jim = User2(email="jim1@test.com").save()
    data, meta = jim.cypher(
        f"MATCH (a) WHERE {db.get_id_method()}(a)=$self RETURN a.email"
    )
    assert data[0][0] == "jim1@test.com"
    assert "a.email" in meta

    data, meta = jim.cypher(
        f"""
            MATCH (a) WHERE {db.get_id_method()}(a)=$self
            MATCH (a)<-[:USER2]-(b)
            RETURN a, b, 3
        """
    )
    assert "a" in meta and "b" in meta


@mark_sync_test
def test_cypher_syntax_error():
    jim = User2(email="jim1@test.com").save()
    try:
        jim.cypher(f"MATCH a WHERE {db.get_id_method()}(a)={{self}} RETURN xx")
    except CypherError as e:
        assert hasattr(e, "message")
        assert hasattr(e, "code")
    else:
        assert False, "CypherError not raised."


@mark_sync_test
@pytest.mark.parametrize("hide_available_pkg", ["pandas"], indirect=True)
def test_pandas_not_installed(hide_available_pkg):
    # We run only the async version, because this fails on second run
    # because import error is thrown only when pandas.py is imported
    if not Util.is_async_code:
        pytest.skip("This test is only")
    with pytest.raises(ImportError):
        with pytest.warns(
            UserWarning,
            match="The neomodel.integration.pandas module expects pandas to be installed",
        ):
            from neomodel.integration.pandas import to_dataframe

            _ = to_dataframe(db.cypher_query("MATCH (a) RETURN a.name AS name"))


@mark_sync_test
def test_pandas_integration():
    pd = pytest.importorskip("pandas", reason="Dependency 'pandas' is required")
    from neomodel.integration.pandas import to_dataframe, to_series

    jimla = UserPandas(email="jimla@test.com", name="jimla").save()
    jimlo = UserPandas(email="jimlo@test.com", name="jimlo").save()

    # Test to_dataframe
    df = to_dataframe(
        db.cypher_query(
            "MATCH (a:UserPandas) RETURN a.name AS name, a.email AS email ORDER BY name"
        )
    )

    assert isinstance(df, pd.DataFrame)
    assert df.shape == (2, 2)
    assert df["name"].tolist() == ["jimla", "jimlo"]

    # Also test passing an index and dtype to to_dataframe
    df = to_dataframe(
        db.cypher_query(
            "MATCH (a:UserPandas) RETURN a.name AS name, a.email AS email ORDER BY name"
        ),
        index=df["email"],
        dtype=str,
    )

    assert df.index.inferred_type == "string"

    # Next test to_series
    series = to_series(
        db.cypher_query("MATCH (a:UserPandas) RETURN a.name AS name ORDER BY name")
    )

    assert isinstance(series, pd.Series)
    assert series.shape == (2,)
    assert df["name"].tolist() == ["jimla", "jimlo"]


@mark_sync_test
@pytest.mark.parametrize("hide_available_pkg", ["numpy"], indirect=True)
def test_numpy_not_installed(hide_available_pkg):
    # We run only the async version, because this fails on second run
    # because import error is thrown only when numpy.py is imported
    if not Util.is_async_code:
        pytest.skip("This test is only")
    with pytest.raises(ImportError):
        with pytest.warns(
            UserWarning,
            match="The neomodel.integration.numpy module expects numpy to be installed",
        ):
            from neomodel.integration.numpy import to_ndarray

            _ = to_ndarray(
                db.cypher_query("MATCH (a) RETURN a.name AS name ORDER BY name")
            )


@mark_sync_test
def test_numpy_integration():
    np = pytest.importorskip("numpy", reason="Dependency 'numpy' is required")
    from neomodel.integration.numpy import to_ndarray

    jimly = UserNP(email="jimly@test.com", name="jimly").save()
    jimlu = UserNP(email="jimlu@test.com", name="jimlu").save()

    array = to_ndarray(
        db.cypher_query(
            "MATCH (a:UserNP) RETURN a.name AS name, a.email AS email ORDER BY name"
        )
    )

    assert isinstance(array, np.ndarray)
    assert array.shape == (2, 2)
    assert array[0][0] == "jimlu"


@mark_sync_test
def test_cypher_query_transaction_timeout_via_config_fires():
    config = get_config()
    original = config.transaction_timeout
    try:
        config.transaction_timeout = 1
        with pytest.raises(ClientError, match="TransactionTimedOut"):
            db.cypher_query("CALL apoc.util.sleep(3000)")
    finally:
        config.transaction_timeout = original


@mark_sync_test
def test_cypher_query_transaction_timeout_via_config_succeeds():
    config = get_config()
    original = config.transaction_timeout
    try:
        config.transaction_timeout = 2
        results, meta = db.cypher_query("CALL apoc.util.sleep(500)")
        assert results is not None
    finally:
        config.transaction_timeout = original


@mark_sync_test
def test_cypher_query_transaction_timeout_with_debug_logging():
    # Regression test: the configured timeout must not break the
    # Cypher debug logging of the executed query
    config = get_config()
    original_timeout = config.transaction_timeout
    original_debug = config.cypher_debug
    try:
        config.cypher_debug = True
        config.transaction_timeout = 5
        results, meta = db.cypher_query("RETURN 1")
        assert results[0][0] == 1
    finally:
        config.transaction_timeout = original_timeout
        config.cypher_debug = original_debug


@mark_sync_test
def test_cypher_debug_log_masks_sensitive_params(caplog):
    import logging

    config = get_config()
    original_debug = config.cypher_debug
    try:
        config.cypher_debug = True
        with caplog.at_level(logging.DEBUG, logger="neomodel.sync_.query"):
            db.cypher_query("RETURN $password AS p", {"password": "s3cr3t"})
        # Only inspect neomodel's own log line: the neo4j driver has separate
        # protocol-level debug logging that echoes raw parameters and is outside
        # neomodel's control.
        logged = "\n".join(
            record.getMessage()
            for record in caplog.records
            if record.name == "neomodel.sync_.query"
        )
        assert "s3cr3t" not in logged
        assert "******" in logged
    finally:
        config.cypher_debug = original_debug


@mark_sync_test
def test_cypher_debug_log_uses_custom_redaction_hook(caplog):
    import logging

    config = get_config()
    original_debug = config.cypher_debug
    original_hook = config.cypher_log_redaction_hook
    try:
        config.cypher_debug = True
        config.cypher_log_redaction_hook = lambda params: {
            key: "<hidden>" for key in params
        }
        with caplog.at_level(logging.DEBUG, logger="neomodel.sync_.query"):
            db.cypher_query("RETURN $email AS e", {"email": "user@example.com"})
        # Only inspect neomodel's own log line (see note above re: the driver's
        # separate protocol-level logging).
        logged = "\n".join(
            record.getMessage()
            for record in caplog.records
            if record.name == "neomodel.sync_.query"
        )
        assert "user@example.com" not in logged
        assert "<hidden>" in logged
    finally:
        config.cypher_debug = original_debug
        config.cypher_log_redaction_hook = original_hook


@mark_sync_test
def test_stream_cypher_query_transaction_timeout_via_config_fires():
    config = get_config()
    original = config.transaction_timeout
    try:
        config.transaction_timeout = 1
        with pytest.raises(ClientError, match="TransactionTimedOut"):
            with db.driver.session(database=db._database_name) as session:
                for _ in db._stream_cypher_query(
                    session,
                    "CALL apoc.util.sleep(3000) RETURN 1",
                    {},
                    handle_unique=True,
                    resolve_objects=False,
                ):
                    pass
    finally:
        config.transaction_timeout = original


# ---------------------------------------------------------------------------
# AsyncQueryRunner unit tests
#
# These drive the query runner against lightweight fakes so the error-handling
# branches (session expiry retry, missing driver, constraint violations during
# streaming) can be exercised without depending on a particular server state.
# ---------------------------------------------------------------------------


class _FakeRecord:
    def __init__(self, values):
        self._values = values

    def values(self):
        return self._values


class _FakeResponse:
    """Minimal stand-in for a neo4j AsyncResult."""

    def __init__(self, rows, keys):
        self._rows = [_FakeRecord(row) for row in rows]
        self._keys = keys

    def keys(self):
        return self._keys

    def __iter__(self):
        self._iter = iter(self._rows)
        return self

    def __next__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopIteration


class _FakeSession:
    def __init__(self, run):
        self._run = run

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def run(self, query=None, parameters=None):
        return self._run()


class _FakeDriver:
    def __init__(self, run):
        self._run = run

    def session(self, **kwargs):
        return _FakeSession(self._run)


class _FakeConnection:
    """Just enough of ConnectionManager for QueryRunner to run."""

    def __init__(self, driver):
        self.driver = driver
        self._active_transaction = None
        self._database_name = "neo4j"
        self.impersonated_user = None
        self._parallel_runtime = False
        self._connection_url = "bolt://user:pass@localhost:7687"
        self._connection_lock = Lock()

    def set_connection(self, url=None, driver=None):
        pass


@mark_sync_test
def test_cypher_query_raises_without_driver():
    # When ensure_connection cannot establish a driver (here set_connection is a
    # no-op), cypher_query must fail loudly rather than dereferencing None.
    connection = _FakeConnection(driver=None)
    connection.set_connection = Mock()
    runner = QueryRunner(connection)

    with pytest.raises(ValueError, match="No driver has been set"):
        runner.cypher_query("RETURN 1")


@mark_sync_test
def test_cypher_query_retries_on_session_expired():
    # The first run raises SessionExpired; with retry_on_session_expire the
    # runner reconnects and replays the query, returning the retried result.
    state = {"expired": False}

    def run():
        if not state["expired"]:
            state["expired"] = True
            raise SessionExpired("connection dropped")
        return _FakeResponse([["after-retry"]], ("value",))

    connection = _FakeConnection(driver=_FakeDriver(run))
    connection.set_connection = Mock()
    runner = QueryRunner(connection)

    results, meta = runner.cypher_query("RETURN 1", retry_on_session_expire=True)

    assert results == [["after-retry"]]
    assert meta == ("value",)
    connection.set_connection.assert_called_once_with(
        url="bolt://user:pass@localhost:7687"
    )


@mark_sync_test
def test_cypher_query_session_expired_not_retried_reraises():
    # Without retry_on_session_expire the SessionExpired must propagate.
    def run():
        raise SessionExpired("connection dropped")

    connection = _FakeConnection(driver=_FakeDriver(run))
    runner = QueryRunner(connection)

    with pytest.raises(SessionExpired):
        runner.cypher_query("RETURN 1")


def _constraint_error(message):
    # Build the error the same way the driver does so .code / .message are set
    # exactly as neomodel inspects them.
    return ClientError._basic_hydrate(
        neo4j_code="Neo.ClientError.Schema.ConstraintValidationFailed",
        message=message,
    )


@mark_sync_test
def test_stream_cypher_query_unique_violation_raises_unique_property():
    # A "already exists with label" constraint error during streaming becomes a
    # UniqueProperty when handle_unique is set.
    def run():
        raise _constraint_error(
            "Node(0) already exists with label `Foo` and property `x`"
        )

    runner = QueryRunner(_FakeConnection(driver=None))

    with pytest.raises(UniqueProperty):
        for _ in runner._stream_cypher_query(
            _FakeSession(run), "Q", {}, handle_unique=True, resolve_objects=False
        ):
            pass


@mark_sync_test
def test_stream_cypher_query_constraint_violation_raises_generic():
    # Any other constraint violation (or handle_unique=False) surfaces as the
    # generic ConstraintValidationFailed.
    def run():
        raise _constraint_error("Some other constraint was violated")

    runner = QueryRunner(_FakeConnection(driver=None))

    with pytest.raises(ConstraintValidationFailed):
        for _ in runner._stream_cypher_query(
            _FakeSession(run), "Q", {}, handle_unique=True, resolve_objects=False
        ):
            pass


@mark_sync_test
def test_cypher_query_client_error_generic():
    """A non-constraint ClientError is propagated unchanged."""
    test_db = Database()

    with patch.object(
        test_db._query, "_run_cypher_query", new_callable=Mock
    ) as mock_run:
        mock_run.side_effect = ClientError("Neo.ClientError.Generic", "message")

        with pytest.raises(ClientError):
            test_db.cypher_query("MATCH (n) RETURN n")
