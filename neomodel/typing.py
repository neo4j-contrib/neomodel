"""Custom types used for annotations."""

from typing import Any, TypedDict

Transformation = TypedDict(
    "Transformation",
    {
        "source": Any,
        "source_prop": str | None,
        "include_in_return": bool | None,
    },
)


Subquery = TypedDict(
    "Subquery",
    {
        "query": str,
        "query_params": dict,
        "return_set": list[str],
        "initial_context": list[Any] | None,
    },
)
