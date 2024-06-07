import pytest
import pytest_asyncio

mark_async_test = pytest.mark.asyncio
mark_async_session_auto_fixture = pytest_asyncio.fixture(scope="session", autouse=True)
mark_sync_session_auto_fixture = pytest.fixture(scope="session", autouse=True)


def mark_sync_test(f):
    return f


class AsyncTestDecorators:
    mark_async_only_test = mark_async_test


class TestDecorators:
    @staticmethod
    def mark_async_only_test(f):
        skip_decorator = pytest.mark.skip("Async only test")
        return skip_decorator(f)
