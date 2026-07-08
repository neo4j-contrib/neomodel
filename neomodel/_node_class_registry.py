"""
Standalone node-class registry.

This maps the set of labels a node carries (and, for database-scoped classes,
the database name) to the neomodel class that should inflate it.

Node classes are discovered **lazily** rather than pushed into a global dict as
a side-effect of class definition. ``get_class`` walks the live subclass tree of
the world's base node class (``AsyncStructuredNode`` / ``StructuredNode``) and
indexes each concrete class by its inherited label set. The index is cached and
rebuilt only when a new class has been defined since the last build (tracked by a
cheap generation counter bumped from the metaclass via :meth:`note_class_defined`).

The cached index holds only **weak references** to the classes, so it never keeps
a class alive: a throwaway/dynamically-created class (common in tests) is
collected as usual and simply drops out of the index.

Consequences of the lazy model:

- **Defining a node class no longer mutates global state.** Redefining a class
  (hot reload, re-import, a class defined twice in a REPL/test) is a non-event:
  the next lookup simply rebuilds from the current live classes. The old
  ``allow_reload`` flag and the definition-time ``NodeClassAlreadyDefined`` are
  therefore gone; a genuine clash between two *distinct* live classes claiming
  the same labels is instead reported at lookup time (see :meth:`get_class`).
- **Relationship models are still registered explicitly.** A relationship's
  ``relation_type`` -> model mapping is established when a ``RelationshipTo``/
  ``RelationshipFrom`` is defined (it is not derivable from the model class
  alone), so it is pushed into ``_node_class_registry`` the way it always was.
  That dict now holds relationship models plus any manual :meth:`register`
  entries; node classes come from the scan.

The class is intentionally world-agnostic (no async/await), so it is shared
verbatim by both APIs. Each world instantiates it once - see
``neomodel/async_/_registry.py`` - passing its own base node class(es), because
the sync classes are transpiled copies of the async ones and share their labels;
a single shared instance would make those duplicates collide.
"""

import weakref
from itertools import combinations
from typing import Any, Callable

from neomodel.exceptions import NodeClassAlreadyDefined
from neomodel.util import deprecated


class _DuplicateLabels:
    """Placeholder stored in the scan index when two distinct live classes claim
    the same label set. Looking such a label set up raises
    :class:`NodeClassAlreadyDefined`.

    Holds *weak* references so it never keeps the clashing classes alive; if one
    side is garbage-collected the clash resolves itself."""

    __slots__ = ("_refs",)

    def __init__(self, classes: list[Any]) -> None:
        self._refs = [weakref.ref(c) for c in classes]

    def add(self, cls: Any) -> None:
        self._refs.append(weakref.ref(cls))

    def live_classes(self) -> list[Any]:
        return [c for c in (ref() for ref in self._refs) if c is not None]


def _same_definition(a: Any, b: Any) -> bool:
    """True when ``a`` and ``b`` are the same class re-executed (a reload): same
    module and qualified name. Such pairs are collapsed (latest wins) rather than
    treated as a clash."""
    return a.__module__ == b.__module__ and a.__qualname__ == b.__qualname__


class NodeClassRegistry:
    def __init__(
        self, node_roots_provider: Callable[[], tuple[type, ...]] | None = None
    ) -> None:
        # Explicit registrations: relationship models (pushed when a relationship
        # is defined) and anything passed to `register()`. Node classes are NOT
        # stored here - they are discovered by scanning. Kept under these names
        # for backward compatibility (exposed as db._NODE_CLASS_REGISTRY etc.).
        self._node_class_registry: dict[frozenset, Any] = {}
        self._db_specific_class_registry: dict[str, dict[frozenset, Any]] = {}

        # Lazy node discovery.
        self._node_roots_provider = node_roots_provider
        self._generation = 0
        self._index_generation = -1
        self._node_index_cache: tuple[dict, dict] | None = None

    # ------------------------------------------------------------------ #
    # Definition-time hook (cheap; no global mutation)
    # ------------------------------------------------------------------ #
    def note_class_defined(self) -> None:
        """Signal that a node class was (re)defined, invalidating the scan cache.

        This is the *only* thing the node metaclass does to the registry - a
        counter bump, not a registration. The next :meth:`get_class` rebuilds the
        index from the live class tree."""
        self._generation += 1

    @deprecated(
        "register() is deprecated: node classes are now discovered automatically "
        "from the live class hierarchy, so explicit registration is unnecessary. "
        "This call still adds an explicit override for backward compatibility."
    )
    def register(self, cls: Any) -> None:
        """Deprecated. Node classes no longer need registering; this now only adds
        an explicit override into the relationship/manual registry."""
        base_label_set = frozenset(cls.inherited_labels())
        if not hasattr(cls, "__target_databases__"):
            self._node_class_registry[base_label_set] = cls
        else:
            for database in cls.__target_databases__:
                self._db_specific_class_registry.setdefault(database, {})[
                    base_label_set
                ] = cls

    # ------------------------------------------------------------------ #
    # Lazy node index
    # ------------------------------------------------------------------ #
    def _iter_registered_node_classes(self) -> Any:
        """Yield every concrete node class reachable from the configured roots.

        A class counts as a concrete (registerable) node exactly when the
        metaclass gave it its own ``__label__`` - abstract nodes never get one -
        which is detected with ``"__label__" in cls.__dict__``. Roots are included
        when they themselves qualify (they usually do, e.g. ``StructuredNode``)."""
        if self._node_roots_provider is None:
            return
        seen: set[int] = set()
        # Preserve definition order (roughly: __subclasses__() appends new
        # classes), so on a reload the later definition wins.
        queue = list(self._node_roots_provider())
        i = 0
        while i < len(queue):
            cls = queue[i]
            i += 1
            if id(cls) in seen:
                continue
            seen.add(id(cls))
            queue.extend(cls.__subclasses__())
            if "__label__" in cls.__dict__:
                yield cls

    def _index_insert(self, idx: dict, labels: frozenset, cls: Any) -> None:
        # Index values are weakref.ref(cls) or a _DuplicateLabels marker.
        existing = idx.get(labels)
        if isinstance(existing, _DuplicateLabels):
            live = existing.live_classes()
            if not any(
                _same_definition(c, cls) or issubclass(cls, c) or issubclass(c, cls)
                for c in live
            ):
                existing.add(cls)
            return

        existing_cls = existing() if isinstance(existing, weakref.ref) else None
        if existing_cls is None:
            # Empty, or the previously-indexed class has been collected.
            idx[labels] = weakref.ref(cls)
        elif (
            existing_cls is cls
            or _same_definition(existing_cls, cls)
            or issubclass(cls, existing_cls)
        ):
            # Same class, a reload, or a more-specific subclass: latest wins.
            idx[labels] = weakref.ref(cls)
        elif issubclass(existing_cls, cls):
            pass  # keep the more-derived class already indexed
        else:
            idx[labels] = _DuplicateLabels([existing_cls, cls])

    def _build_node_index(self) -> tuple[dict, dict]:
        global_idx: dict[frozenset, Any] = {}
        db_idx: dict[str, dict[frozenset, Any]] = {}
        for cls in self._iter_registered_node_classes():
            labels = frozenset(cls.inherited_labels())
            targets = getattr(cls, "__target_databases__", None)
            if not targets:
                self._index_insert(global_idx, labels, cls)
            else:
                for database in targets:
                    self._index_insert(db_idx.setdefault(database, {}), labels, cls)
        return global_idx, db_idx

    def _node_index(self) -> tuple[dict, dict]:
        if self._node_index_cache is None or self._index_generation != self._generation:
            self._node_index_cache = self._build_node_index()
            self._index_generation = self._generation
        return self._node_index_cache

    # ------------------------------------------------------------------ #
    # Index-value helpers
    #
    # An index value is one of: a strong class (only in the explicit
    # relationship/manual registry), a ``weakref.ref`` to a class (scan index),
    # a ``_DuplicateLabels`` marker, or ``None``.
    # ------------------------------------------------------------------ #
    @staticmethod
    def _peek(value: Any) -> Any:
        """Return a representative live class for an index value, or ``None`` if
        absent/collected. Never raises (used for filtering and messages)."""
        if value is None:
            return None
        if isinstance(value, _DuplicateLabels):
            live = value.live_classes()
            return live[0] if live else None
        if isinstance(value, weakref.ref):
            return value()
        return value  # strong class from the explicit registry

    def _deref(self, value: Any) -> Any:
        """Return the resolved class for an index value, ``None`` if
        absent/collected, or raise if the labels are claimed by two live classes."""
        if isinstance(value, _DuplicateLabels):
            live = value.live_classes()
            if len(live) <= 1:
                return live[0] if live else None
            raise NodeClassAlreadyDefined(
                live[-1],
                self.snapshot_node_registry(),
                self.snapshot_db_registry(),
            )
        if isinstance(value, weakref.ref):
            return value()
        return value

    # ------------------------------------------------------------------ #
    # Optional-label matching (base set + a combination of optional labels)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _optional_labels(cls: Any) -> frozenset:
        get_optionals = getattr(cls, "inherited_optional_labels", None)
        if callable(get_optionals):
            return frozenset(get_optionals())
        return frozenset()

    def _match_with_optional_labels(
        self, label_set: frozenset, registry: dict[frozenset, Any]
    ) -> Any | None:
        """Find the registered value whose base label set is a subset of
        ``label_set`` and whose declared optional labels cover the remaining
        labels. Prefers the most specific (largest) base set. Returns the raw
        index value (the caller dereferences it)."""
        labels = tuple(label_set)
        # Try larger base sets first so the most specific class wins. The full
        # set (size == len) is the exact match handled by the caller, so start
        # one below it. Bounded by 2**len(labels) - the number of labels on an
        # actual node is small, unlike the number of declared optional labels.
        for size in range(len(labels) - 1, 0, -1):
            for combo in combinations(labels, size):
                base = frozenset(combo)
                cls = self._peek(registry.get(base))
                if cls is not None and (label_set - base) <= self._optional_labels(cls):
                    return registry.get(base)
        return None

    def get_class(self, label_set: frozenset, database_name: str | None) -> Any | None:
        """Return the class for ``label_set`` (preferring explicit registrations,
        then discovered node classes; global before database-scoped), or ``None``
        if unknown.

        An exact base-label match is tried first; failing that, the labels are
        resolved as a base set plus a combination of that class's optional labels.
        Raises :class:`NodeClassAlreadyDefined` if the labels are claimed by two
        distinct live classes.
        """
        label_set = frozenset(label_set)
        global_idx, db_idx = self._node_index()
        db_explicit = (
            self._db_specific_class_registry.get(database_name)
            if database_name is not None
            else None
        )
        db_scan = db_idx.get(database_name) if database_name is not None else None
        sources = [
            s
            for s in (self._node_class_registry, global_idx, db_explicit, db_scan)
            if s is not None
        ]

        # Exact base-label match (the common case: a node with no optional labels).
        for source in sources:
            hit = self._deref(source.get(label_set))
            if hit is not None:
                return hit

        # Resolve base + optional-label combinations lazily.
        for source in sources:
            hit = self._deref(self._match_with_optional_labels(label_set, source))
            if hit is not None:
                return hit

        return None

    # ------------------------------------------------------------------ #
    # Snapshots (for error messages: a merged view of everything known)
    # ------------------------------------------------------------------ #
    def _snapshot(self, idx: dict[frozenset, Any]) -> dict[frozenset, Any]:
        out = {}
        for key, value in idx.items():
            cls = self._peek(value)
            if cls is not None:
                out[key] = cls
        return out

    def snapshot_node_registry(self) -> dict[frozenset, Any]:
        global_idx, _ = self._node_index()
        merged = self._snapshot(global_idx)
        merged.update(self._node_class_registry)
        return merged

    def snapshot_db_registry(self) -> dict[str, dict[frozenset, Any]]:
        _, db_idx = self._node_index()
        merged: dict[str, dict[frozenset, Any]] = {
            db: self._snapshot(entries) for db, entries in db_idx.items()
        }
        for db, entries in self._db_specific_class_registry.items():
            merged.setdefault(db, {}).update(entries)
        return merged
