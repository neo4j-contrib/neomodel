"""Custom types used for annotations."""

from typing import Any, Dict, List, Optional, TypedDict

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
        "query_params": Dict,
        "return_set": List[str],
        "initial_context": Optional[List[Any]],
    },
)
