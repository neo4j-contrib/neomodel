"""Custom types used for annotations."""

from typing import Any, Optional, TypedDict

Transformation = TypedDict(
    "Transformation",
    {
        "source": Any,
        "source_prop": Optional[str],
        "include_in_return": Optional[bool],
    },
)


Subquery = TypedDict(
    "Subquery",
    {
        "query": str,
        "query_params": dict,
        "return_set": list[str],
        "initial_context": Optional[list[Any]],
    },
)
