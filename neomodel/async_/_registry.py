"""
Per-world instance of the node-class registry.

The async and sync APIs each get their own registry instance: the sync model
classes are transpiled copies of the async ones and carry identical labels, so a
single shared instance would make them collide. This module transpiles to
``neomodel/sync_/_registry.py``, giving the sync world its own ``registry``.

The registry discovers node classes by walking the live subclass tree of this
world's base node class. That base is provided lazily (the base class does not
exist yet when this module is imported by ``node.py``), so ``_node_roots`` is a
callable resolved at scan time rather than at construction.
"""

from neomodel._node_class_registry import NodeClassRegistry


def _node_roots() -> tuple[type, ...]:
    from neomodel.async_.node import AsyncStructuredNode

    return (AsyncStructuredNode,)


registry = NodeClassRegistry(node_roots_provider=_node_roots)
