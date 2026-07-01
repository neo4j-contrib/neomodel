import warnings
from enum import IntEnum
from types import FrameType
from typing import Any, Callable

from neo4j.graph import Entity


class RelationshipDirection(IntEnum):
    """Enum representing the direction of relationships in Neo4j."""

    OUTGOING = 1
    INCOMING = -1
    EITHER = 0


def deprecated(message: str) -> Callable:
    # pylint:disable=invalid-name
    def f__(f: Callable) -> Callable:
        def f_(*args, **kwargs) -> Any:
            warnings.warn(message, category=DeprecationWarning, stacklevel=2)
            return f(*args, **kwargs)

        f_.__name__ = f.__name__
        f_.__doc__ = f.__doc__
        f_.__dict__.update(f.__dict__)
        return f_

    return f__


def classproperty(f: Callable) -> Any:
    class cpf:
        def __init__(self, getter: Callable) -> None:
            self.getter = getter

        def __get__(self, obj: Any, type: Any | None = None) -> Any:
            return self.getter(type)

    return cpf(f)


# Just used for error messages
class _UnsavedNode:
    def __repr__(self) -> str:
        return "<unsaved node>"

    def __str__(self) -> str:
        return self.__repr__()


def escape_identifier(identifier: str) -> str:
    """
    Backtick-escape an identifier (label, relationship type, property name,
    index/constraint name, ...) for safe interpolation into a Cypher query,
    doubling any embedded backticks so the identifier cannot be terminated early.
    """
    return "`" + str(identifier).replace("`", "``") + "`"


def escape_label(label: str) -> str:
    """Backtick-escape a label. Alias of :func:`escape_identifier`."""
    return escape_identifier(label)


def escape_cypher_string_literal(value: str) -> str:
    """
    Escape a value for safe interpolation inside a single-quoted Cypher string
    literal. Use this where parameters are not accepted, e.g. the ``OPTIONS``
    map of index creation statements. Backslashes and single quotes are escaped
    so the literal cannot be terminated early or inject extra syntax.
    """
    return str(value).replace("\\", "\\\\").replace("'", "\\'")


def get_graph_entity_properties(entity: Entity) -> dict:
    """
    Get the properties from a neo4j.graph.Entity (neo4j.graph.Node or neo4j.graph.Relationship) object.
    """
    return entity._properties


def enumerate_traceback(initial_frame: FrameType | None = None) -> Any:
    depth, frame = 0, initial_frame
    while frame is not None:
        yield depth, frame
        frame = frame.f_back
        depth += 1


def version_tag_to_integer(version_tag: str) -> int:
    """
    Converts a version string to an integer representation to allow for quick comparisons between versions.

    :param a_version_string: The version string to be converted (e.g. '5.4.0')
    :type a_version_string: str
    :return: An integer representation of the version string (e.g. '5.4.0' --> 50400)
    :rtype: int
    """
    components = version_tag.split(".")
    while len(components) < 3:
        components.append("0")
    num = 0
    for index, component in enumerate(components):
        # Aura started adding a -aura suffix in version numbers, like "5.14-aura"
        # This will strip the suffix to allow for proper comparison : 14 instead of 14-aura
        if "-" in component:
            component = component.split("-")[0]
        num += (100 ** ((len(components) - 1) - index)) * int(component)
    return num
