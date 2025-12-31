"""
Additional tests for neomodel.sync_.core module to improve coverage.
"""

from test._async_compat import mark_sync_test
from unittest.mock import Mock, patch

import pytest
from neo4j.exceptions import ClientError

from neomodel.sync_.database import Database, ensure_connection
from neomodel.sync_.transaction import TransactionProxy


@mark_sync_test
def test_ensure_connection_decorator_no_driver():
    """Test ensure_connection decorator when driver is None."""

    class MockDB:
        def __init__(self):
            self.driver = None

        def set_connection(self, **kwargs):
            # Dummy implementation for testing
            pass

        @ensure_connection
        def test_method(self):
            return "success"

    test_db = MockDB()
    with patch.object(
        test_db, "set_connection", new_callable=Mock
    ) as mock_set_connection:
        result = test_db.test_method()
        assert result == "success"
        mock_set_connection.assert_called_once_with(
            url="bolt://neo4j:foobarbaz@localhost:7687"
        )


@mark_sync_test
def test_ensure_connection_decorator_with_driver():
    """Test ensure_connection decorator when driver is set."""

    class MockDB:
        def __init__(self):
            self.driver = "existing_driver"

        @ensure_connection
        def test_method(self):
            return "success"

    test_db = MockDB()
    result = test_db.test_method()
    assert result == "success"


@mark_sync_test
def test_clear_neo4j_database():
    """Test clear_neo4j_database method."""
    test_db = Database()

    with patch.object(test_db, "cypher_query", new_callable=Mock) as mock_cypher:
        with patch.object(
            test_db, "drop_constraints", new_callable=Mock
        ) as mock_drop_constraints:
            with patch.object(
                test_db, "drop_indexes", new_callable=Mock
            ) as mock_drop_indexes:
                test_db.clear_neo4j_database(clear_constraints=True, clear_indexes=True)

                mock_cypher.assert_called_once()
                mock_drop_constraints.assert_called_once()
                mock_drop_indexes.assert_called_once()


@mark_sync_test
def test_drop_constraints():
    """Test drop_constraints method."""
    test_db = Database()

    mock_results = [
        {"name": "constraint1", "labelsOrTypes": ["Label1"], "properties": ["prop1"]},
        {"name": "constraint2", "labelsOrTypes": ["Label2"], "properties": ["prop2"]},
    ]

    with patch.object(test_db, "cypher_query", new_callable=Mock) as mock_cypher:
        mock_cypher.return_value = (
            mock_results,
            ["name", "labelsOrTypes", "properties"],
        )

        test_db.drop_constraints(quiet=False)

        # Should call LIST_CONSTRAINTS_COMMAND and DROP_CONSTRAINT_COMMAND for each constraint
        assert mock_cypher.call_count == 3  # 1 for list + 2 for drop


@mark_sync_test
def test_drop_indexes():
    """Test drop_indexes method."""
    test_db = Database()

    mock_indexes = [
        {"name": "index1", "labelsOrTypes": ["Label1"], "properties": ["prop1"]},
        {"name": "index2", "labelsOrTypes": ["Label2"], "properties": ["prop2"]},
    ]

    with patch.object(test_db, "list_indexes", new_callable=Mock) as mock_list_indexes:
        mock_list_indexes.return_value = mock_indexes

        with patch.object(test_db, "cypher_query", new_callable=Mock) as mock_cypher:
            test_db.drop_indexes(quiet=False)

            # Should call DROP_INDEX_COMMAND for each index
            assert mock_cypher.call_count == 2


@mark_sync_test
def test_remove_all_labels():
    """Test remove_all_labels method."""
    test_db = Database()

    with patch.object(
        test_db, "drop_constraints", new_callable=Mock
    ) as mock_drop_constraints:
        with patch.object(
            test_db, "drop_indexes", new_callable=Mock
        ) as mock_drop_indexes:
            with patch("sys.stdout") as mock_stdout:
                test_db.remove_all_labels()

                mock_drop_constraints.assert_called_once_with(
                    quiet=False, stdout=mock_stdout
                )
                mock_drop_indexes.assert_called_once_with(
                    quiet=False, stdout=mock_stdout
                )


@mark_sync_test
def test_install_all_labels():
    """Test install_all_labels method."""
    test_db = Database()

    class MockNode:
        def __init__(self, name):
            self.__name__ = name

        @classmethod
        def install_labels(cls, quiet=True, stdout=None):
            pass

    with patch("neomodel.sync_.node.StructuredNode", MockNode):
        with patch("sys.stdout"):
            test_db.install_all_labels()

            # Should call install_labels on each node class
            assert True  # Test passes if no exception is raised


@mark_sync_test
def test_proxy_aenter_parallel_runtime_warning():
    """Test TransactionProxy __enter__ with parallel runtime warning."""
    test_db = Database()
    proxy = TransactionProxy(test_db, parallel_runtime=True)

    with patch.object(
        test_db, "parallel_runtime_available", new_callable=Mock
    ) as mock_available:
        mock_available.return_value = False

        with patch("warnings.warn") as mock_warn:
            with patch.object(test_db, "begin", new_callable=Mock) as mock_begin:
                proxy.__enter__()

                # Filter for the specific parallel runtime warning
                parallel_runtime_calls = [
                    call
                    for call in mock_warn.call_args_list
                    if "Parallel runtime is only available" in str(call[0][0])
                ]
                assert len(parallel_runtime_calls) == 1
                mock_begin.assert_called_once()


@mark_sync_test
def test_proxy_aexit_with_exception():
    """Test TransactionProxy __exit__ with exception."""
    test_db = Database()
    proxy = TransactionProxy(test_db)

    with patch.object(test_db, "rollback", new_callable=Mock) as mock_rollback:
        with patch.object(test_db, "commit", new_callable=Mock) as mock_commit:
            # Test with exception
            proxy.__exit__(ValueError, ValueError("test"), None)
            mock_rollback.assert_called_once()
            mock_commit.assert_not_called()


@mark_sync_test
def test_proxy_aexit_success():
    """Test TransactionProxy __exit__ with success."""
    test_db = Database()
    proxy = TransactionProxy(test_db)

    with patch.object(test_db, "rollback", new_callable=Mock) as mock_rollback:
        with patch.object(test_db, "commit", new_callable=Mock) as mock_commit:
            mock_commit.return_value = "bookmarks"

            proxy.__exit__(None, None, None)
            mock_rollback.assert_not_called()
            mock_commit.assert_called_once()
            assert proxy.last_bookmarks == "bookmarks"


@mark_sync_test
def test_proxy_call_decorator():
    """Test TransactionProxy __call__ decorator."""
    test_db = Database()
    proxy = TransactionProxy(test_db)

    def test_func():
        return "success"

    decorated = proxy(test_func)
    assert callable(decorated)

    # Test that the decorated function works
    with patch.object(proxy, "__enter__", new_callable=Mock) as mock_enter:
        with patch.object(proxy, "__exit__", new_callable=Mock):
            mock_enter.return_value = proxy
            result = decorated()
            assert result == "success"


@mark_sync_test
def test_cypher_query_client_error_generic():
    """Test cypher_query with generic ClientError."""
    test_db = Database()

    with patch.object(test_db, "_run_cypher_query", new_callable=Mock) as mock_run:
        client_error = ClientError("Neo.ClientError.Generic", "message")
        mock_run.side_effect = client_error

        with pytest.raises(ClientError):
            test_db.cypher_query("MATCH (n) RETURN n")
