from typing import Any
from typing_extensions import TypedDict

class Transformation(TypedDict):
    source: Any
    source_prop: str | None
    include_in_return: bool | None

class Subquery(TypedDict):
    query: str
    query_params: dict
    return_set: list[str]
    initial_context: list[Any] | None
