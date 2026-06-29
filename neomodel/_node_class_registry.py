"""
Standalone node-class registry.

This maps the set of labels a node carries (and, for database-scoped classes,
the database name) to the neomodel class that should inflate it. The logic used
to live as state and methods on the ``Database`` god object; it is extracted
here so model definition and object resolution no longer have to reach into the
connection object.

Only a class's *base* label set (its inherited labels) is stored. A class may
also declare ``__optional_labels__`` - extra labels a node might additionally
carry - and a node can present any combination of them. Rather than
pre-materialising every base+optional combination at registration time (which is
exponential in the number of optional labels), combinations are resolved lazily
at lookup: see :meth:`NodeClassRegistry.get_class`.

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
        # base label-set -> class, for classes that are not database-scoped
        self._node_class_registry: dict[frozenset, Any] = {}
        # database name -> (base label-set -> class), for __target_databases__ classes
        self._db_specific_class_registry: dict[str, dict[frozenset, Any]] = {}

    def register(self, cls: Any) -> None:
        """Register a node/relationship class under its base (inherited) label
        set. Optional-label combinations are not stored; they are resolved at
        lookup time by :meth:`get_class`."""
        base_label_set = frozenset(cls.inherited_labels())
        allow_reload = get_config().allow_reload

        if not hasattr(cls, "__target_databases__"):
            self._register_one(
                self._node_class_registry, base_label_set, cls, allow_reload
            )
        else:
            for database in cls.__target_databases__:
                db_registry = self._db_specific_class_registry.setdefault(database, {})
                self._register_one(
                    db_registry, base_label_set, cls, allow_reload, database=database
                )

    def _register_one(
        self,
        registry: dict[frozenset, Any],
        label_set: frozenset,
        cls: Any,
        allow_reload: bool,
        database: str | None = None,
    ) -> None:
        if label_set not in registry:
            registry[label_set] = cls
            return
        if allow_reload:
            self._warn_reloading(cls, database=database)
            registry[label_set] = cls
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

    @staticmethod
    def _optional_labels(cls: Any) -> frozenset:
        get_optionals = getattr(cls, "inherited_optional_labels", None)
        if callable(get_optionals):
            return frozenset(get_optionals())
        return frozenset()

    def _match_with_optional_labels(
        self, label_set: frozenset, registry: dict[frozenset, Any]
    ) -> Any | None:
        """Find the registered class whose base label set is a subset of
        ``label_set`` and whose declared optional labels cover the remaining
        labels. Prefers the most specific (largest) base set."""
        labels = tuple(label_set)
        # Try larger base sets first so the most specific class wins. The full
        # set (size == len) is the exact match handled by the caller, so start
        # one below it. Bounded by 2**len(labels) - the number of labels on an
        # actual node is small, unlike the number of declared optional labels.
        for size in range(len(labels) - 1, 0, -1):
            for combo in combinations(labels, size):
                base = frozenset(combo)
                cls = registry.get(base)
                if cls is not None and (label_set - base) <= self._optional_labels(cls):
                    return cls
        return None

    def get_class(self, label_set: frozenset, database_name: str | None) -> Any | None:
        """Return the class for ``label_set`` (preferring the global registry,
        then the database-scoped one), or ``None`` if unknown.

        An exact base-label match is tried first; failing that, the labels are
        resolved as a base set plus a combination of that class's optional
        labels.
        """
        label_set = frozenset(label_set)
        db_registry = (
            self._db_specific_class_registry.get(database_name)
            if database_name is not None
            else None
        )

        # Exact base-label match (the common case: a node with no optional labels).
        cls = self._node_class_registry.get(label_set)
        if cls is not None:
            return cls
        if db_registry is not None:
            cls = db_registry.get(label_set)
            if cls is not None:
                return cls

        # Resolve base + optional-label combinations lazily.
        cls = self._match_with_optional_labels(label_set, self._node_class_registry)
        if cls is not None:
            return cls
        if db_registry is not None:
            cls = self._match_with_optional_labels(label_set, db_registry)
            if cls is not None:
                return cls

        return None
