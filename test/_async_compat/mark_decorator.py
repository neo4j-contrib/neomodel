import pytest

mark_async_test = pytest.mark.asyncio


def mark_sync_test(f):
    return f


class AsyncTestDecorators:
    mark_async_only_test = mark_async_test


class TestDecorators:
    @staticmethod
    def mark_async_only_test(f):
        skip_decorator = pytest.mark.skip("Async only test")
        return skip_decorator(f)
