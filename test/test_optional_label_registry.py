"""
Unit tests for lazy optional-label resolution in the node-class registry.

A class's base label set is registered once; base+optional combinations are
resolved at lookup time rather than pre-materialised at registration (which is
exponential in the number of optional labels). DB-independent; it exercises the
shared registry logic via the sync instance.
"""

import gc

from neomodel import StringProperty, StructuredNode
from neomodel.sync_._registry import registry


class RegistryWidget(StructuredNode):
    __optional_labels__ = ["Shiny", "Heavy", "Fragile"]
    name = StringProperty()


BASE = frozenset(RegistryWidget.inherited_labels())  # {"RegistryWidget"}


# Two distinct classes (different qualnames) that reuse the same label. Because
# they live in different function scopes they never coexist, mirroring the same
# label being reused by throwaway classes in two different test modules.
def _define_first_weak():
    class WeakReuse(StructuredNode):
        __label__ = "WeakRefReuseLabel"

    return WeakReuse


def _define_second_weak():
    class WeakReuse(StructuredNode):
        __label__ = "WeakRefReuseLabel"

    return WeakReuse


def test_base_label_set_resolves():
    assert registry.get_class(BASE, None) is RegistryWidget


def test_optional_label_combinations_resolve():
    assert registry.get_class(BASE | {"Shiny"}, None) is RegistryWidget
    assert registry.get_class(BASE | {"Shiny", "Heavy"}, None) is RegistryWidget
    assert (
        registry.get_class(BASE | {"Shiny", "Heavy", "Fragile"}, None) is RegistryWidget
    )


def test_non_optional_extra_label_does_not_resolve():
    assert registry.get_class(BASE | {"NotDeclared"}, None) is None


def test_combinations_are_not_pre_materialised():
    # Node classes are discovered by scanning the live hierarchy and indexed by
    # their base label set only; the 2**3 optional combinations are resolved at
    # lookup time, never materialised in the index.
    global_index, _ = registry._node_index()
    assert BASE in global_index
    assert (BASE | {"Shiny"}) not in global_index
    assert (BASE | {"Shiny", "Heavy", "Fragile"}) not in global_index


def test_index_holds_weak_references():
    # The scan index does not pin the classes it indexes: a collected class drops
    # out, so a different class can reuse its label without a spurious clash. This
    # is what lets throwaway test classes in different modules share a label.
    label = frozenset(["WeakRefReuseLabel"])

    first = _define_first_weak()
    assert registry.get_class(label, None) is first

    del first
    gc.collect()

    second = _define_second_weak()
    # The first class was collected, so resolving the shared label returns the
    # second one instead of raising NodeClassAlreadyDefined.
    assert registry.get_class(label, None) is second
