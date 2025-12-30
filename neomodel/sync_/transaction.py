"""
Transaction management for the neomodel module.
"""

import warnings
from functools import wraps
from inspect import iscoroutinefunction
from typing import Any, Callable

from neo4j.api import Bookmarks
from neo4j.exceptions import ClientError

from neomodel._async_compat.util import Util
from neomodel.constants import NOT_COROUTINE_ERROR
from neomodel.exceptions import UniqueProperty
from neomodel.sync_.database import Database


class TransactionProxy:
    def __init__(
        self,
        db: Database,
        access_mode: str | None = None,
        parallel_runtime: bool | None = False,
    ):
        self.db: Database = db
        self.access_mode: str | None = access_mode
        self.parallel_runtime: bool | None = parallel_runtime
        self.bookmarks: Bookmarks | None = None
        self.last_bookmarks: Bookmarks | None = None

    def __enter__(self) -> "TransactionProxy":
        if self.parallel_runtime and not self.db.parallel_runtime_available():
            warnings.warn(
                "Parallel runtime is only available in Neo4j Enterprise Edition 5.13 and above. "
                "Reverting to default runtime.",
                UserWarning,
            )
            self.parallel_runtime = False
        self.db._parallel_runtime = self.parallel_runtime
        self.db.begin(access_mode=self.access_mode, bookmarks=self.bookmarks)
        self.bookmarks = None
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.db._parallel_runtime = False
        if exc_value:
            self.db.rollback()

        if (
            exc_type is ClientError
            and exc_value.code == "Neo.ClientError.Schema.ConstraintValidationFailed"
        ):
            raise UniqueProperty(exc_value.message)

        if not exc_value:
            self.last_bookmarks = self.db.commit()

    def __call__(self, func: Callable) -> Callable:
        if Util.is_async_code and not iscoroutinefunction(func):
            raise TypeError(NOT_COROUTINE_ERROR)

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Callable:
            with self:
                return func(*args, **kwargs)

        return wrapper

    @property
    def with_bookmark(self) -> "BookmarkingAsyncTransactionProxy":
        return BookmarkingAsyncTransactionProxy(self.db, self.access_mode)


class BookmarkingAsyncTransactionProxy(TransactionProxy):
    def __call__(self, func: Callable) -> Callable:
        if Util.is_async_code and not iscoroutinefunction(func):
            raise TypeError(NOT_COROUTINE_ERROR)

        def wrapper(*args: Any, **kwargs: Any) -> tuple[Any, None]:
            self.bookmarks = kwargs.pop("bookmarks", None)

            with self:
                result = func(*args, **kwargs)
                self.last_bookmarks = None

            return result, self.last_bookmarks

        return wrapper


class ImpersonationHandler:
    def __init__(self, db: Database, impersonated_user: str):
        self.db = db
        self.impersonated_user = impersonated_user

    def __enter__(self) -> "ImpersonationHandler":
        self.db.impersonated_user = self.impersonated_user
        return self

    def __exit__(
        self, exception_type: Any, exception_value: Any, exception_traceback: Any
    ) -> None:
        self.db.impersonated_user = None

        print("\nException type:", exception_type)
        print("\nException value:", exception_value)
        print("\nTraceback:", exception_traceback)

    def __call__(self, func: Callable) -> Callable:
        def wrapper(*args: Any, **kwargs: Any) -> Callable:
            with self:
                return func(*args, **kwargs)

        return wrapper
