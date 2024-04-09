import typing as t


class AsyncUtil:
    is_async_code: t.ClassVar = True


class Util:
    is_async_code: t.ClassVar = False
