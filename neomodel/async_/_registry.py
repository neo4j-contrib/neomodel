"""
Per-world instance of the node-class registry.

The async and sync APIs each get their own registry instance: the sync model
classes are transpiled copies of the async ones and carry identical labels, so a
single shared instance would make them collide. This module transpiles to
``neomodel/sync_/_registry.py``, giving the sync world its own ``registry``.
"""

from neomodel._node_class_registry import NodeClassRegistry

registry = NodeClassRegistry()
