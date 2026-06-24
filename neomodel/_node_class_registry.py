"""
Standalone node-class registry.

This maps the set of labels a node carries (and, for database-scoped classes,
the database name) to the neomodel class that should inflate it. The logic used
to live as state and methods on the ``Database`` god object; it is extracted
here so model definition and object resolution no longer have to reach into the
connection object.

The class is intentionally world-agnostic (no async/await), so it is shared
verbatim by both the async and sync APIs. Each world instantiates it once - see
``neomodel/async_/_registry.py`` - because the sync classes are transpiled
copies of the async ones and share their labels; a single shared instance would
make those duplicates collide.
"""

import warnings
from itertools import combinations
from typing import Any

from neomodel.config import get_config
from neomodel.exceptions import NodeClassAlreadyDefined


class NodeClassRegistry:
    def __init__(self) -> None:
        # label-set -> class, for classes that are not database-scoped
        self._node_class_registry: dict[frozenset, Any] = {}
        # database name -> (label-set -> class), for __target_databases__ classes
        self._db_specific_class_registry: dict[str, dict[frozenset, Any]] = {}

    def register(self, cls: Any) -> None:
        """Register a node/relationship class under every label combination it
        can present (base labels plus each subset of its optional labels)."""
        base_label_set = frozenset(cls.inherited_labels())
        optional_label_set = set(cls.inherited_optional_labels())

        # Construct all possible combinations of labels + optional labels
        possible_label_combinations = [
            frozenset(set(x).union(base_label_set))
            for i in range(1, len(optional_label_set) + 1)
            for x in combinations(optional_label_set, i)
        ]
        possible_label_combinations.append(base_label_set)

        # Check if config allows reloading
        allow_reload = get_config().allow_reload

        for label_set in possible_label_combinations:
            if not hasattr(cls, "__target_databases__"):
                if label_set not in self._node_class_registry:
                    self._node_class_registry[label_set] = cls
                else:
                    if allow_reload:
                        self._warn_reloading(cls)
                        self._node_class_registry[label_set] = cls
                    else:
                        raise NodeClassAlreadyDefined(
                            cls,
                            self._node_class_registry,
                            self._db_specific_class_registry,
                        )
            else:
                for database in cls.__target_databases__:
                    if database not in self._db_specific_class_registry:
                        self._db_specific_class_registry[database] = {}
                    if label_set not in self._db_specific_class_registry[database]:
                        self._db_specific_class_registry[database][label_set] = cls
                    else:
                        if allow_reload:
                            self._warn_reloading(cls, database=database)
                            self._db_specific_class_registry[database][label_set] = cls
                        else:
                            raise NodeClassAlreadyDefined(
                                cls,
                                self._node_class_registry,
                                self._db_specific_class_registry,
                            )

    @staticmethod
    def _warn_reloading(cls: Any, database: str | None = None) -> None:
        node_class_labels = ",".join(cls.inherited_labels())
        suffix = f" for database {database}" if database is not None else ""
        warnings.warn(
            f"Class {cls.__module__}.{cls.__name__} with labels {node_class_labels} "
            f"is being reloaded{suffix}. Updating class registry.",
            UserWarning,
            stacklevel=4,
        )

    def get_class(self, label_set: frozenset, database_name: str | None) -> Any | None:
        """Return the class registered for ``label_set`` (preferring the global
        registry, then the database-scoped one), or ``None`` if unknown."""
        if label_set in self._node_class_registry:
            return self._node_class_registry[label_set]
        if (
            database_name is not None
            and database_name in self._db_specific_class_registry
            and label_set in self._db_specific_class_registry[database_name]
        ):
            return self._db_specific_class_registry[database_name][label_set]
        return None
