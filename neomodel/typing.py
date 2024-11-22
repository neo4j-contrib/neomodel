"""Custom types used for annotations."""

from typing import Any, Optional, TypedDict

Transformation = TypedDict(
    "Transformation",
    {
        "source": Any,
        "source_prop": Optional[str],
        "distinct": Optional[bool],
        "include_in_return": Optional[bool],
    },
)
