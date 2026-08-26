"""
Unit tests for :class:`neomodel._node_class_registry.NodeClassRegistry` internals
- lazy scanning, the weak-reference index, and duplicate detection.

These are world-agnostic and DB-independent. Each test builds an *isolated*
registry over a throwaway abstract base class, so the scan sees only the classes
defined by that test rather than the whole process-wide model hierarchy.
"""

import gc

import pytest

from neomodel import StructuredNode
from neomodel._node_class_registry import NodeClassRegistry, _DuplicateLabels
from neomodel.exceptions import NodeClassAlreadyDefined


def _abstract_base():
    """A fresh abstract StructuredNode subclass with an empty subclass tree."""

    class _Base(StructuredNode):
        __abstract_node__ = True

    return _Base


def _registry_over(base):
    return NodeClassRegistry(node_roots_provider=lambda: (base,))


def test_get_class_without_roots_returns_none():
    # A registry with no roots provider discovers nothing.
    reg = NodeClassRegistry()
    assert reg.get_class(frozenset(["Anything"]), None) is None


def test_register_is_deprecated_but_still_maps_global_and_db():
    base = _abstract_base()
    reg = _registry_over(base)

    class Plain(base):
        __label__ = "RegPlain"

    class Scoped(base):
        __label__ = "RegScoped"
        __target_databases__ = ["dbx"]

    with pytest.warns(DeprecationWarning):
        reg.register(Plain)
    with pytest.warns(DeprecationWarning):
        reg.register(Scoped)

    # register() pushes into the explicit (relationship/manual) registry.
    assert reg._node_class_registry[frozenset(["RegPlain"])] is Plain
    assert reg._db_specific_class_registry["dbx"][frozenset(["RegScoped"])] is Scoped
    # The database-specific explicit entry is merged into the snapshot.
    assert frozenset(["RegScoped"]) in reg.snapshot_db_registry()["dbx"]


def test_three_distinct_classes_same_label_form_a_duplicate():
    base = _abstract_base()
    reg = _registry_over(base)

    class DupOne(base):
        __label__ = "Tri"

    class DupTwo(base):
        __label__ = "Tri"

    class DupThree(base):
        __label__ = "Tri"

    global_idx, _ = reg._node_index()
    entry = global_idx[frozenset(["Tri"])]
    assert isinstance(entry, _DuplicateLabels)
    assert len(entry.live_classes()) == 3
    with pytest.raises(NodeClassAlreadyDefined):
        reg.get_class(frozenset(["Tri"]), None)


def test_subclass_is_not_added_to_existing_duplicate():
    base = _abstract_base()
    reg = _registry_over(base)

    class A(base):
        __label__ = "Sub"

    class B(base):
        __label__ = "Sub"  # A and B are distinct -> a duplicate

    class C(A):
        __label__ = "Sub"  # a subclass of A carrying the same label

    entry = reg._node_index()[0][frozenset(["Sub"])]
    assert isinstance(entry, _DuplicateLabels)
    live = entry.live_classes()
    # C is subsumed by A (a subclass), so it is not a new clashing member.
    assert C not in live and set(live) == {A, B}


def test_index_insert_keeps_the_more_derived_class():
    base = _abstract_base()
    reg = _registry_over(base)

    class Parent(base):
        __label__ = "MD"

    class Child(Parent):
        __label__ = "MD"

    labels = frozenset(["MD"])
    idx: dict = {}
    reg._index_insert(idx, labels, Child)  # more-derived indexed first
    reg._index_insert(idx, labels, Parent)  # parent must not displace it
    assert reg._peek(idx[labels]) is Child


def test_duplicate_resolves_to_survivor_when_one_side_is_collected():
    base = _abstract_base()
    reg = _registry_over(base)

    def _make_gone():
        class Gone(base):
            __label__ = "Reduce"

        return Gone

    def _make_kept():
        class Kept(base):
            __label__ = "Reduce"

        return Kept

    gone = _make_gone()
    kept = _make_kept()
    assert isinstance(reg._node_index()[0][frozenset(["Reduce"])], _DuplicateLabels)

    del gone
    gc.collect()

    # With one side collected the clash resolves to the survivor (no raise).
    assert reg.get_class(frozenset(["Reduce"]), None) is kept


def test_diamond_inheritance_is_scanned_once():
    base = _abstract_base()
    reg = _registry_over(base)

    class Left(base):
        __label__ = "L"

    class Right(base):
        __label__ = "R"

    class Diamond(Left, Right):
        __label__ = "D"

    # Diamond is reachable via both Left and Right; the scan's `seen` guard must
    # visit it only once and still resolve it correctly.
    assert reg.get_class(frozenset(["D", "L", "R"]), None) is Diamond


def test_helpers_on_non_class_values():
    reg = NodeClassRegistry()

    class Strong:
        pass

    # A strong class value (as held in the explicit registry) passes through _peek.
    assert reg._peek(Strong) is Strong
    # An object without inherited_optional_labels contributes no optional labels.
    assert reg._optional_labels(object()) == frozenset()
